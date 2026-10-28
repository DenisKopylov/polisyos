"""Actual request/snapshot controls for registered SQL capture."""

import sqlite3

import pytest

import polisyos.fabric.api as fabric_api
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.contracts.fabric import DataViewRequestRef
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector
from polisyos.ir.model_layer.queries import DataFilter, DataViewRequest
from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort


def _request(store, *, filters=None):
    value = DataViewRequest(
        request_id="registered-sql",
        view_type="table",
        metrics=["policy_inputs"],
        filters=filters or [],
    )
    ref = store.put_json(
        value,
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
        return_selected_profile=True,
    )
    return DataViewRequestRef.model_validate(ref.model_dump(mode="python"))


def _port(tmp_path):
    database = tmp_path / "rows.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL)")
        connection.execute("INSERT INTO policy_inputs VALUES (12.5)")
    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "policy_inputs"}),
    )
    return DefaultFabricPort(
        connector_registry=registry, connector_id="sql.query", require_fresh_registered_sql=True
    )


def test_real_snapshot_rejects_mutated_observed_rows(tmp_path, monkeypatch):
    """Changing the result after SQL but before persistence must not bind capture."""
    store = FileSystemCAS(tmp_path / "cas")
    request = _request(store)
    port = _port(tmp_path)
    execute = fabric_api._execute_registered_sql

    def mutate(*args, **kwargs):
        observed = execute(*args, **kwargs)
        observed.result.data.loc[0, "income"] = 999.0
        return observed

    monkeypatch.setattr(fabric_api, "_execute_registered_sql", mutate)
    with pytest.raises(ValueError, match="registered_sql_execution_changed"):
        port._snapshot_with_execution(store, request)


def test_registered_snapshot_refuses_filter_the_legacy_compiler_discards(tmp_path):
    """An unsupported filter cannot be erased before source-profile validation."""
    store = FileSystemCAS(tmp_path / "cas")
    request = _request(store, filters=[DataFilter(column="income", op="!=", value="12.5")])
    with pytest.raises(ValueError, match="registered_sql_requested_scope_not_executed"):
        _port(tmp_path).snapshot(store, request)


def test_registered_sql_and_federation_are_mutually_exclusive():
    with pytest.raises(ValueError, match="mutually exclusive"):
        DefaultFabricPort(
            connector_registry=ConnectorRegistry(),
            connector_id="sql.query",
            require_fresh_registered_sql=True,
            federation=object(),
        )


def test_registered_snapshot_reports_source_freshness_and_completeness_unknown(tmp_path):
    """A successful bounded SQL read cannot prove external freshness or completeness."""
    from polisyos.core.artifacts import load_core_json_artifact

    store = FileSystemCAS(tmp_path / "cas")
    snapshot_ref = _port(tmp_path).snapshot(store, _request(store))
    snapshot = load_core_json_artifact(store, snapshot_ref)
    report_ref = ArtifactRef.model_validate(snapshot["quality_report_ref"])
    report = load_core_json_artifact(store, report_ref)
    assert store.get_manifest(report_ref).artifact_schema == SchemaInfo(
        name="polisyos.fabric.DataQualityReport", version="1.1"
    )
    assert report["freshness_status"]["level"] == "unknown"
    assert report["freshness_status"]["is_fresh"] is False
    assert report["score"] == 0.0
    assert report["tier"] == "unverified"
    assert "source_completeness_unknown" in report["quality_flags"]

    from polisyos.scientist.nodes.builtins.governance.data_plane_gate import (
        _quality_report_from_dict,
        _QualityReportArtifact,
    )

    _QualityReportArtifact.model_validate(report, strict=True)
    assert _quality_report_from_dict(report).completeness_score == 0.0
    report["freshness_status"]["is_fresh"] = True
    with pytest.raises(ValueError, match="unknown_freshness_cannot_be_fresh"):
        _QualityReportArtifact.model_validate(report, strict=True)
    assert _quality_report_from_dict(report).completeness_score == 0.0


def test_quality_schema_reader_supports_old_and_unknown_freshness_versions():
    """The epoch owner recognizes both the historic and new selected schemas."""
    from polisyos.core.contracts.epoch import (
        _known_epoch_statement_manifest_schema,
        acquisition_artifact_codec,
    )

    codec = acquisition_artifact_codec("fabric.quality_report", media_type="application/json")
    assert codec is not None
    accepted = _known_epoch_statement_manifest_schema("fabric.quality_report", codec)
    assert accepted == (
        SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.0"),
        SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.1"),
    )


def test_registered_snapshot_retains_nulls_from_actual_sql(tmp_path):
    """The selected CAS row must retain an actual SQL NULL field."""
    from polisyos.core.artifacts import load_core_json_artifact

    database = tmp_path / "nulls.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL, note TEXT)")
        connection.execute("INSERT INTO policy_inputs VALUES (12.5, NULL)")
    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "policy_inputs"}),
    )
    store = FileSystemCAS(tmp_path / "cas")
    port = DefaultFabricPort(
        connector_registry=registry, connector_id="sql.query", require_fresh_registered_sql=True
    )
    snapshot_ref, observed = port._snapshot_with_execution(store, _request(store))
    snapshot = load_core_json_artifact(store, snapshot_ref)
    payload_ref = ArtifactRef.model_validate(snapshot["data_ref"])
    assert load_core_json_artifact(store, payload_ref) == [{"income": 12.5, "note": None}]
    assert observed is not None
    assert observed.columns == ("income", "note")
    assert len(observed.dtypes) == 2
    schema_ref = ArtifactRef.model_validate(snapshot["data_schema_ref"])
    schema = load_core_json_artifact(store, schema_ref)
    assert store.get_manifest(schema_ref).artifact_schema == SchemaInfo(
        name="polisyos.fabric.DataSchema", version="1.1"
    )
    assert schema["sql_columns"] == [
        {"name": name, "dtype": dtype}
        for name, dtype in zip(observed.columns, observed.dtypes, strict=True)
    ]


def test_registered_snapshot_refuses_altered_persisted_rows(tmp_path, monkeypatch):
    """A successful CAS write cannot self-attest its payload contents."""
    store = FileSystemCAS(tmp_path / "cas")
    port = _port(tmp_path)
    request = _request(store)
    put_json = store.put_json

    def alter(value, options, *args, **kwargs):
        if options.kind == "fabric.tabular_payload":
            value = [{"income": 999.0}]
        return put_json(value, options, *args, **kwargs)

    monkeypatch.setattr(store, "put_json", alter)
    with pytest.raises(ValueError, match="registered_sql_output_binding_not_established"):
        port.snapshot(store, request)


def test_registered_snapshot_refuses_caller_reconstructed_observation(tmp_path, monkeypatch):
    """A matching public data object cannot stand in for the driver observation."""
    from dataclasses import replace

    store = FileSystemCAS(tmp_path / "cas")
    port = _port(tmp_path)
    request = _request(store)
    execute = fabric_api._execute_registered_sql

    def forge(*args, **kwargs):
        return replace(execute(*args, **kwargs))

    monkeypatch.setattr(fabric_api, "_execute_registered_sql", forge)
    with pytest.raises(ValueError, match="registered_sql_execution_not_observed"):
        port.snapshot(store, request)


def test_registered_snapshot_does_not_infer_survey_design_from_columns(tmp_path):
    """A survey-like name is not a survey design or workflow grant."""
    from polisyos.core.artifacts import load_core_json_artifact

    database = tmp_path / "survey.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(survey_year INTEGER, wave INTEGER)")
        connection.execute("INSERT INTO policy_inputs VALUES (2020, 1)")
    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "policy_inputs"}),
    )
    store = FileSystemCAS(tmp_path / "cas")
    port = DefaultFabricPort(
        connector_registry=registry, connector_id="sql.query", require_fresh_registered_sql=True
    )
    snapshot_ref = port.snapshot(store, _request(store))
    snapshot = load_core_json_artifact(store, snapshot_ref)
    assert snapshot["stats"]["registered_sql_data_shape_basis"] == "not_established"
    assert "data_shape" not in snapshot["stats"]
    assert not any(note.startswith("allowed_workflows=") for note in snapshot["notes"])


def _storage_only_registered_source(tmp_path, *, expected_query, use_key="foundry.selected_basis"):
    """Use a synthetic issuer solely for component wiring, not Runtime proof."""
    from polisyos.core.contracts.decision_validity import RegisteredSQLUseContract
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLViewContract
    from polisyos.scientist.validation.decision_validity import DecisionValidityService
    from polisyos.scientist.validation.source_admission_port import (
        _bind_source_admission_authority,
    )

    store = FileSystemCAS(tmp_path / "cas", tenant_id="tenant-a", cell_id="cell-a")
    port = _port(tmp_path)
    config = port._connector_registry.get_default_config("sql.query")
    assert config is not None
    view = RegisteredSQLViewContract(
        provider_id="test-provider",
        connector_id="sql.query",
        dataset_id="policy_inputs",
        config_fingerprint=config.cache_scope_fingerprint,
        statement=expected_query,
        page_size=100,
    )
    view_ref = store.put_json(
        view,
        ArtifactWriteOptions(
            kind=RegisteredSQLViewContract.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=RegisteredSQLViewContract.ARTIFACT_SCHEMA_NAME, version="1.0"),
        ),
        return_selected_profile=True,
    )
    use_ref = store.put_json(
        RegisteredSQLUseContract(use_key=use_key),
        ArtifactWriteOptions(
            kind=RegisteredSQLUseContract.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=RegisteredSQLUseContract.ARTIFACT_SCHEMA_NAME, version="1.0"),
        ),
        return_selected_profile=True,
    )
    authority = _bind_source_admission_authority(
        issuer_key="storage-unit-not-runtime-authority",
        tenant_id="tenant-a",
        cell_id="cell-a",
        provider_id="test-provider",
        registration_key="source-a",
        effective_view_contract_ref=view_ref,
        use_contract_ref=use_ref,
        permitted_operations=frozenset({"genesis", "admit", "withdraw", "read_event"}),
        validate_issuer=lambda: None,
    )
    owner = DecisionValidityService(store)
    registration = owner.register_materialization_source(
        authority,
        event_id="genesis-a",
        registration_key="source-a",
        effective_view_contract_ref=view_ref,
        use_contract_ref=use_ref,
    )
    return store, port, authority, owner, registration


def test_sql_producer_binds_actual_snapshot_to_existing_owner_and_retries(tmp_path):
    """Component fixture only; installed Runtime authority is a separate test."""
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer

    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    request_ref = _request(store)
    producer = RegisteredSQLProducer(port=port, owner=owner, authority=authority)
    receipt, materialization, binding_ref = producer.acquire_and_admit(
        store=store,
        request_ref=request_ref,
        registration=registration,
        event_id="admit-a",
        occurrence_id="occurrence-a",
        expected_predecessor=registration.event_ref,
    )
    assert receipt.carrier is not None
    assert type(request_ref) is DataViewRequestRef
    assert type(materialization.request_ref) is ArtifactRef
    assert type(materialization.snapshot_ref) is ArtifactRef
    assert materialization.request_ref.model_dump(mode="json") == request_ref.model_dump(
        mode="json"
    )
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts.decision_validity import RegisteredSQLAdmissionBinding

    protected = validate_core_model_json_artifact(RegisteredSQLAdmissionBinding, store, binding_ref)
    assert protected.receipt == receipt
    assert protected.materialization == materialization
    import json

    counterfeit = protected.model_dump(mode="json")
    counterfeit["materialization"]["occurrence_id"] = "other-occurrence"
    with pytest.raises(ValueError, match="registered_sql_binding_receipt_mismatch"):
        RegisteredSQLAdmissionBinding.model_validate_json(json.dumps(counterfeit), strict=True)
    assert owner.read_source_current_use((receipt.carrier,)).status == "current"
    assert producer.acquire_and_admit(
        store=store,
        request_ref=request_ref,
        registration=registration,
        event_id="admit-a",
        occurrence_id="occurrence-a",
        expected_predecessor=registration.event_ref,
    ) == (receipt, materialization, binding_ref)
    with pytest.raises(ValueError, match="registered_sql_retry_command_mismatch"):
        producer.acquire_and_admit(
            store=store,
            request_ref=request_ref,
            registration=registration,
            event_id="admit-a",
            occurrence_id="occurrence-b",
            expected_predecessor=registration.event_ref,
        )
    withdrawn = owner.transition_materialization(
        authority,
        event_id="withdraw-a",
        expected_predecessor=receipt.event_ref,
        operation="withdraw",
        target=receipt.carrier,
    )
    assert withdrawn.carrier is not None
    assert owner.read_source_current_use((receipt.carrier,)).status == "withdrawn"
    assert producer.acquire_and_admit(
        store=store,
        request_ref=request_ref,
        registration=registration,
        event_id="admit-a",
        occurrence_id="occurrence-a",
        expected_predecessor=registration.event_ref,
    ) == (receipt, materialization, binding_ref)


def test_sql_producer_rejects_executed_view_mismatch(tmp_path):
    """A real driver read for table A cannot satisfy a registered view for B."""
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer

    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "other_inputs" LIMIT 100'
    )
    producer = RegisteredSQLProducer(port=port, owner=owner, authority=authority)
    with pytest.raises(ValueError, match="registered_sql_view_not_executed"):
        producer.acquire_and_admit(
            store=store,
            request_ref=_request(store),
            registration=registration,
            event_id="admit-a",
            occurrence_id="occurrence-a",
            expected_predecessor=registration.event_ref,
        )
    assert owner.resolve_source_materialization_event(authority, event_id="admit-a") is None


def test_sql_producer_refuses_missing_capture_input_edge(tmp_path, monkeypatch):
    """The capture must bind every actual snapshot/view/use input edge."""
    from dataclasses import replace

    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer

    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    request_ref = _request(store)
    original_put = store.put_json

    def omit_edge(value, options, *args, **kwargs):
        if options.kind == "fabric.registered_sql_capture":
            options = replace(options, inputs=options.inputs[:-1])
        return original_put(value, options, *args, **kwargs)

    monkeypatch.setattr(store, "put_json", omit_edge)
    producer = RegisteredSQLProducer(port=port, owner=owner, authority=authority)
    with pytest.raises(ValueError, match="registered_sql_capture_binding_not_established"):
        producer.acquire_and_admit(
            store=store,
            request_ref=request_ref,
            registration=registration,
            event_id="admit-a",
            occurrence_id="occurrence-a",
            expected_predecessor=registration.event_ref,
        )
    assert owner.resolve_source_materialization_event(authority, event_id="admit-a") is None


@pytest.mark.parametrize("change", ["output", "request_profile"])
def test_sql_producer_refuses_rewritten_capture_content(tmp_path, monkeypatch, change):
    """A valid selected capture with changed content cannot authorize the real read."""
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer

    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    request_ref = _request(store)
    original_put = store.put_json

    def rewrite_capture(value, options, *args, **kwargs):
        if options.kind == "fabric.registered_sql_capture":
            if change == "output":
                value = value.model_copy(update={"output_sha256": "sha256:" + "0" * 64})
            else:
                different_ref = value.request_ref.model_copy(
                    update={"manifest_profile_sha256": "sha256:" + "0" * 64}
                )
                value = value.model_copy(update={"request_ref": different_ref})
        return original_put(value, options, *args, **kwargs)

    monkeypatch.setattr(store, "put_json", rewrite_capture)
    with pytest.raises(ValueError, match="registered_sql_capture_binding_not_established"):
        RegisteredSQLProducer(port=port, owner=owner, authority=authority).acquire_and_admit(
            store=store,
            request_ref=request_ref,
            registration=registration,
            event_id="rewritten-capture",
            occurrence_id="actual-occurrence",
            expected_predecessor=registration.event_ref,
        )
    assert (
        owner.resolve_source_materialization_event(authority, event_id="rewritten-capture") is None
    )


def test_foundry_binding_carries_the_actual_single_sql_source(tmp_path):
    """Selected Foundry input bindings preserve the producer's exact snapshot."""
    from polisyos.core.artifacts.manifest import artifact_ref_identity_key
    from polisyos.core.contracts.foundry import FoundryInputBindingRule
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.foundry.data_plane.bindings import build_input_bindings, load_input_bindings
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer

    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    producer = RegisteredSQLProducer(port=port, owner=owner, authority=authority)
    receipt, materialization, source_ref = producer.acquire_and_admit(
        store=store,
        request_ref=_request(store),
        registration=registration,
        event_id="admit-a",
        occurrence_id="occurrence-a",
        expected_predecessor=registration.event_ref,
    )
    assert receipt.carrier is not None
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    built = build_input_bindings(
        store,
        data_snapshot_ref=materialization.snapshot_ref,
        registry_bundle_ref=registry.bundle_ref,
        rules=[
            FoundryInputBindingRule(
                binding_id="income",
                source_path="income",
                target_slot_id="agents.income",
            )
        ],
        registered_sql_admission_ref=source_ref,
        return_selected_profile=True,
    )
    bindings = load_input_bindings(store, built.input_bindings_ref)
    assert bindings.schema_version == "1.1"
    assert artifact_ref_identity_key(bindings.registered_sql_admission_ref) == (
        artifact_ref_identity_key(source_ref)
    )
    with pytest.raises(ValueError, match="registered_sql_binding_source_read_not_established"):
        build_input_bindings(
            store,
            data_snapshot_ref=materialization.snapshot_ref,
            registry_bundle_ref=registry.bundle_ref,
            rules=[
                FoundryInputBindingRule(
                    binding_id="defaulted",
                    source_path="missing_income",
                    target_slot_id="agents.income",
                    required=False,
                    default_value=12.5,
                )
            ],
            registered_sql_admission_ref=source_ref,
            return_selected_profile=True,
        )
    edges = store.get_manifest(built.input_bindings_ref).inputs
    edge = next(row for row in edges if row.role == "input.registered_sql_admission_ref")
    assert edge.artifact_id == source_ref.artifact_id
    assert edge.manifest_profile_sha256 == source_ref.manifest_profile_sha256

    unselected = ArtifactRef.model_validate(
        source_ref.model_dump(mode="python") | {"manifest_profile_sha256": None}
    )
    with pytest.raises(ValueError, match="registered_sql_binding_selected_profile_required"):
        build_input_bindings(
            store,
            data_snapshot_ref=materialization.snapshot_ref,
            registry_bundle_ref=registry.bundle_ref,
            registered_sql_admission_ref=unselected,
            return_selected_profile=True,
        )


def test_registered_sql_binding_refuses_a_different_persisted_state(tmp_path, monkeypatch):
    """A selected SQL input cannot be paired with another otherwise-valid state."""
    from polisyos.core.contracts.foundry import FoundryInputBindingRule
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.foundry.contracts.state import GlobalState
    from polisyos.foundry.data_plane import bindings as binding_module
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer

    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    producer = RegisteredSQLProducer(port=port, owner=owner, authority=authority)
    _, materialization, source_ref = producer.acquire_and_admit(
        store=store,
        request_ref=_request(store),
        registration=registration,
        event_id="admit-a",
        occurrence_id="occurrence-a",
        expected_predecessor=registration.event_ref,
    )
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    original_put = binding_module.put_state_snapshot

    def substitute(cas, *, state, step, inputs, return_selected_profile):
        del state
        return original_put(
            cas,
            state=GlobalState.empty(1, 1),
            step=step,
            inputs=inputs,
            return_selected_profile=return_selected_profile,
        )

    monkeypatch.setattr(binding_module, "put_state_snapshot", substitute)
    with pytest.raises(ValueError, match="registered_sql_binding_state_replay_mismatch"):
        binding_module.build_input_bindings(
            store,
            data_snapshot_ref=materialization.snapshot_ref,
            registry_bundle_ref=registry.bundle_ref,
            rules=[
                FoundryInputBindingRule(
                    binding_id="income",
                    source_path="income",
                    target_slot_id="agents.income",
                )
            ],
            registered_sql_admission_ref=source_ref,
            return_selected_profile=True,
        )


def test_registered_sql_binding_reaches_real_foundry_execution_basis(tmp_path):
    """Component-only chain: real SQL, synthetic issuer, Foundry, owner withdrawal.

    This does not establish Runtime issuer provenance, a job handoff, or served
    current-use. Its issuer fixture intentionally exercises the private unit seam.
    """
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.artifacts.manifest import artifact_ref_identity_key
    from polisyos.core.contracts.decision_validity import RegisteredSQLAdmissionBinding
    from polisyos.core.contracts.foundry import FoundryInputBindingRule, SimulationResult
    from polisyos.foundry.data_plane.bindings import build_input_bindings
    from polisyos.foundry.execute import admit_execution_source
    from polisyos.foundry.execute.api import execute
    from polisyos.foundry.execute.executor import load_state_snapshot
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer
    from tests.unit.foundry.calibration.test_identifiability_response_basis import _native_fixture

    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    producer = RegisteredSQLProducer(port=port, owner=owner, authority=authority)
    receipt, materialization, source_ref = producer.acquire_and_admit(
        store=store,
        request_ref=_request(store),
        registration=registration,
        event_id="admit-a",
        occurrence_id="occurrence-a",
        expected_predecessor=registration.event_ref,
    )
    assert receipt.carrier is not None
    _, template_result_ref, _ = _native_fixture(tmp_path, store=store)
    template = admit_execution_source(store, template_result_ref)
    assert template.basis is not None
    inputs = build_input_bindings(
        store,
        data_snapshot_ref=materialization.snapshot_ref,
        registry_bundle_ref=template.basis.binding_registry_ref,
        rules=[
            FoundryInputBindingRule(
                binding_id="reported_income",
                source_path="income",
                target_slot_id="agents.reported_income",
            )
        ],
        registered_sql_admission_ref=source_ref,
        return_selected_profile=True,
    )
    request = template.basis.request.model_copy(
        update={"input_bindings_ref": inputs.input_bindings_ref}
    )
    executed = execute(store, request)
    assert executed.ok and executed.simulation_result_ref is not None
    result_ref = executed.simulation_result_ref
    result = validate_core_model_json_artifact(SimulationResult, store, result_ref)
    poststate = load_state_snapshot(store, snapshot_ref=result.state_snapshot_ref)
    # The actual fiscal mechanism reads reported_income; this makes A a real
    # consumed input, rather than an unused scheduling/source prerequisite.
    assert float(poststate.government_balance) == pytest.approx(6.25)
    original_bytes = store.get_bytes(result_ref)
    admitted = admit_execution_source(store, result_ref)
    assert admitted.basis is not None and admitted.basis_ref is not None
    carried_ref = admitted.basis.registered_sql_admission_ref
    assert carried_ref is not None
    assert artifact_ref_identity_key(carried_ref) == artifact_ref_identity_key(source_ref)
    source = validate_core_model_json_artifact(RegisteredSQLAdmissionBinding, store, carried_ref)
    assert source.receipt == receipt and source.materialization == materialization
    assert any(
        edge.role == "basis.source.registered_sql_admission"
        and edge.artifact_id == source_ref.artifact_id
        and edge.manifest_profile_sha256 == source_ref.manifest_profile_sha256
        for edge in store.get_manifest(admitted.basis_ref).inputs
    )
    assert owner.read_source_current_use((source.receipt.carrier,)).status == "current"
    owner.transition_materialization(
        authority,
        event_id="withdraw-a",
        expected_predecessor=receipt.event_ref,
        operation="withdraw",
        target=receipt.carrier,
    )
    assert owner.read_source_current_use((source.receipt.carrier,)).status == "withdrawn"
    assert store.get_bytes(result_ref) == original_bytes
    assert admit_execution_source(store, result_ref).basis == admitted.basis


def test_concurrent_same_event_recovers_one_sql_occurrence(tmp_path, monkeypatch):
    """One event's overlapping retries share the original committed occurrence."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer

    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    request_ref = _request(store)
    producer = RegisteredSQLProducer(port=port, owner=owner, authority=authority)
    first_entered = threading.Event()
    release_first = threading.Event()
    counter_lock = threading.Lock()
    captures = 0
    original = DefaultFabricPort._snapshot_with_execution

    def hold_first(actual_port, actual_store, actual_request, **kwargs):
        nonlocal captures
        with counter_lock:
            captures += 1
            ordinal = captures
        if ordinal == 1:
            first_entered.set()
            if not release_first.wait(10):
                raise AssertionError("concurrent retry did not finish")
        return original(actual_port, actual_store, actual_request, **kwargs)

    monkeypatch.setattr(DefaultFabricPort, "_snapshot_with_execution", hold_first)

    def call():
        return producer.acquire_and_admit(
            store=store,
            request_ref=request_ref,
            registration=registration,
            event_id="admit-a",
            occurrence_id="occurrence-a",
            expected_predecessor=registration.event_ref,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(call)
        assert first_entered.wait(10)
        second = pool.submit(call)
        try:
            with pytest.raises(ValueError, match="source_admission_acquisition_busy"):
                second.result(timeout=5)
        finally:
            release_first.set()
        first_result = first.result(timeout=30)

    retry_result = call()
    assert first_result == retry_result
    assert captures == 1
    assert owner.current_source_admission_head(authority, registration) == first_result[0].event_ref


def test_stale_source_predecessor_is_refused_before_driver_read(tmp_path, monkeypatch):
    """Known stale commands cannot trigger a new SQL acquisition."""
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer

    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    producer = RegisteredSQLProducer(port=port, owner=owner, authority=authority)

    def must_not_read(*_args, **_kwargs):
        raise AssertionError("stale predecessor reached the SQL driver")

    monkeypatch.setattr(DefaultFabricPort, "_snapshot_with_execution", must_not_read)
    with pytest.raises(ValueError, match="source_admission_predecessor_gap"):
        producer.acquire_and_admit(
            store=store,
            request_ref=_request(store),
            registration=registration,
            event_id="stale-event",
            occurrence_id="stale-occurrence",
            expected_predecessor="sha256:" + "0" * 64,
        )
    assert owner.resolve_source_materialization_event(authority, event_id="stale-event") is None


def test_registered_view_rejects_unapplied_query_parameters():
    """The supported direct SQL profile has no driver parameters to erase."""
    from pydantic import ValidationError

    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLViewContract

    with pytest.raises(ValidationError):
        RegisteredSQLViewContract(
            provider_id="provider",
            connector_id="sql.query",
            dataset_id="policy_inputs",
            config_fingerprint="sha256:" + "a" * 64,
            statement='SELECT * FROM "policy_inputs" LIMIT 3',
            page_size=3,
            parameters=("unapplied",),
        )


def test_registered_view_refuses_same_query_on_a_different_database(tmp_path, monkeypatch):
    """Identical table/query text does not re-register another source incarnation."""
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer

    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    other = tmp_path / "other.sqlite"
    with sqlite3.connect(other) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL)")
        connection.execute("INSERT INTO policy_inputs VALUES (12.5)")
    port._connector_registry.set_default_config(
        "sql.query",
        ConnectionConfig(url=f"sqlite:///{other}", headers={"X-SQL-Table": "policy_inputs"}),
    )
    producer = RegisteredSQLProducer(port=port, owner=owner, authority=authority)

    def must_not_connect(*_args, **_kwargs):
        raise AssertionError("wrong source reached the SQLite driver")

    monkeypatch.setattr(sqlite3, "connect", must_not_connect)
    with pytest.raises(ValueError, match="registered_sql_view_not_executed"):
        producer.acquire_and_admit(
            store=store,
            request_ref=_request(store),
            registration=registration,
            event_id="different-source",
            occurrence_id="different-source",
            expected_predecessor=registration.event_ref,
        )
    assert (
        owner.resolve_source_materialization_event(authority, event_id="different-source") is None
    )


def test_guarded_owner_refuses_callback_only_materialization(tmp_path):
    """A real prior capture cannot be reminted by a no-op validator."""
    from polisyos.runtime.http.resilience import _bind_registered_source_owner, guard_runtime_cas
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer
    from polisyos.scientist.validation.decision_validity import DecisionValidityService
    from polisyos.scientist.validation.source_admission_port import (
        _capture_registered_materialization,
    )

    store, port, authority, original_owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    guarded = guard_runtime_cas(store)
    owner = DecisionValidityService(guarded)
    _bind_registered_source_owner(owner=owner, guarded_store=guarded)
    receipt, materialization, _ = RegisteredSQLProducer(
        port=port, owner=original_owner, authority=authority
    ).acquire_and_admit(
        store=store,
        request_ref=_request(store),
        registration=registration,
        event_id="actual-admission",
        occurrence_id="actual-occurrence",
        expected_predecessor=registration.event_ref,
    )
    callback_calls = 0

    def pretend_producer():
        nonlocal callback_calls
        callback_calls += 1

    fake = _capture_registered_materialization(
        authority=authority, materialization=materialization, validate_capture=pretend_producer
    )
    assert callback_calls == 1
    with pytest.raises(ValueError, match="registered_sql_producer_provenance_not_established"):
        owner.admit_materialization(
            fake, event_id="forged-admission", expected_predecessor=receipt.event_ref
        )
    assert callback_calls == 1
    assert (
        original_owner.resolve_source_materialization_event(authority, event_id="forged-admission")
        is None
    )


def test_scientist_node_consumes_selected_sql_source_into_foundry_binding(tmp_path):
    """The ordinary binding node carries the real single-source transport."""
    import logging

    from polisyos.core.artifacts.manifest import artifact_ref_identity_key
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.foundry.data_plane.bindings import load_input_bindings
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer
    from polisyos.scientist.nodes.builtins.data.bind_foundry_inputs import BindFoundryInputsNode
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    _, materialization, source_ref = RegisteredSQLProducer(
        port=port, owner=owner, authority=authority
    ).acquire_and_admit(
        store=store,
        request_ref=_request(store),
        registration=registration,
        event_id="node-source",
        occurrence_id="node-occurrence",
        expected_predecessor=registration.event_ref,
    )
    registry = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="registered-sql-node")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.sql-node"))
    state = ExperimentState(
        run_id="registered-sql-node",
        inputs={
            "registered_sql_admission_ref": source_ref,
            "data_snapshot_ref": materialization.snapshot_ref,
            "registry_bundle_ref": registry,
        },
        params={
            "foundry_input_binding_rules": [
                {"binding_id": "income", "source_path": "income", "target_slot_id": "agents.income"}
            ]
        },
    )
    outcome = BindFoundryInputsNode(strict_model_spec_match=False).execute(ctx, state)
    assert outcome.status == "ok", outcome.error
    ref = outcome.state.inputs["input_bindings_ref"]
    assert ref.manifest_profile_sha256 is not None
    bindings = load_input_bindings(store, ref)
    assert artifact_ref_identity_key(bindings.registered_sql_admission_ref) == (
        artifact_ref_identity_key(source_ref)
    )
    assert artifact_ref_identity_key(bindings.data_snapshot_ref) == (
        artifact_ref_identity_key(materialization.snapshot_ref)
    )


def _isolated_sql_workflow_app(tmp_path, monkeypatch):
    """Select a real owner-built candidate catalog under this test's directory."""
    from polisyos.runtime.http.app import create_runtime_api_app
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_catalog_serving_source,
    )

    root = tmp_path.resolve(strict=True)
    curated = root / "empty-curated"
    production = root / "empty-production-data"
    curated.mkdir()
    production.mkdir()
    monkeypatch.setenv("POLISYOS_CACHE_HOME", str(root / "catalog-cache"))
    monkeypatch.setenv("POLISYOS_CURATED_DIR", str(curated))
    monkeypatch.setenv("POLISYOS_PRODUCTION_DATA_ROOT", str(production))
    selection, source = build_candidate_cycle_catalog_serving_source(root)
    app = create_runtime_api_app(
        cas_root=root / "cas",
        core_runs_root=root / "runs",
        repo_root=root,
        catalog_source_selection=selection,
    )
    return app, source


def test_actual_workflow_creation_reopens_sql_history_and_current_use(tmp_path, monkeypatch):
    """The job payload records the actual owner-admitted carrier and snapshot."""
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.control import WorkflowDataSourceBinding, WorkflowRunRequest
    from polisyos.core.contracts.decision_validity import RegisteredSQLAdmissionBinding
    from polisyos.core.security import tenant_scope
    from polisyos.runtime.http.errors import RuntimeHTTPError
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    receipt, materialization, source_ref = RegisteredSQLProducer(
        port=port, owner=owner, authority=authority
    ).acquire_and_admit(
        store=store,
        request_ref=_request(store),
        registration=registration,
        event_id="workflow-source",
        occurrence_id="workflow-occurrence",
        expected_predecessor=registration.event_ref,
    )
    original = validate_core_model_json_artifact(RegisteredSQLAdmissionBinding, store, source_ref)
    changed = original.model_copy(update={"expected_predecessor": "sha256:" + "0" * 64})
    manifest = store.get_manifest(source_ref)
    counterfeit = store.put_json(
        changed,
        ArtifactWriteOptions(
            kind=RegisteredSQLAdmissionBinding.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=RegisteredSQLAdmissionBinding.ARTIFACT_SCHEMA_NAME, version="1.0"
            ),
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    app, catalog_source = _isolated_sql_workflow_app(tmp_path, monkeypatch)
    with TestClient(app):
        assert app.state._control_service.catalog_serving_source.database_path == (
            catalog_source.database_path
        )
        service = app.state._control_service
        principal = RuntimePrincipal(
            subject="analyst", tenant_id="tenant-a", cell_id="cell-a", authenticated=True
        )

        def launch(ref):
            return service.launch_workflow_run(
                WorkflowRunRequest(
                    data_source=WorkflowDataSourceBinding(registered_sql_admission_ref=ref)
                ),
                principal=principal,
            )

        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            launched = launch(source_ref)
            job = service._control_store.get_job(launched.job_id)
            payload = service._load_payload_ref(
                job.payload_ref, kind="runtime.control_job_payload.workflow_run"
            )
            inputs = payload["state_payload"]["inputs"]
            assert inputs["registered_sql_admission_ref"] == source_ref.model_dump(mode="json")
            assert inputs["data_snapshot_ref"] == materialization.snapshot_ref.model_dump(
                mode="json"
            )
            with pytest.raises(RuntimeHTTPError) as bad_history:
                launch(counterfeit)
            assert bad_history.value.code == "registered_sql_workflow_source_not_established"
            owner.transition_materialization(
                authority,
                event_id="workflow-withdrawal",
                expected_predecessor=receipt.event_ref,
                operation="withdraw",
                target=receipt.carrier,
            )
            with pytest.raises(RuntimeHTTPError) as withdrawn:
                launch(source_ref)
            assert withdrawn.value.code == "registered_sql_workflow_source_not_established"


def test_workflow_refuses_admitted_source_for_a_different_use(tmp_path, monkeypatch):
    """An any-active contract for another purpose cannot authorize Foundry use."""
    from fastapi.testclient import TestClient

    from polisyos.core.contracts.control import WorkflowDataSourceBinding, WorkflowRunRequest
    from polisyos.core.security import tenant_scope
    from polisyos.runtime.http.errors import RuntimeHTTPError
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100', use_key="debug_only"
    )
    _, _, ref = RegisteredSQLProducer(
        port=port, owner=owner, authority=authority
    ).acquire_and_admit(
        store=store,
        request_ref=_request(store),
        registration=registration,
        event_id="wrong-purpose",
        occurrence_id="wrong-purpose",
        expected_predecessor=registration.event_ref,
    )
    app, catalog_source = _isolated_sql_workflow_app(tmp_path, monkeypatch)
    with TestClient(app):
        assert app.state._control_service.catalog_serving_source.database_path == (
            catalog_source.database_path
        )
        principal = RuntimePrincipal(
            subject="analyst", tenant_id="tenant-a", cell_id="cell-a", authenticated=True
        )
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            with pytest.raises(RuntimeHTTPError) as refused:
                app.state._control_service.launch_workflow_run(
                    WorkflowRunRequest(
                        data_source=WorkflowDataSourceBinding(registered_sql_admission_ref=ref)
                    ),
                    principal=principal,
                )
        assert refused.value.code == "registered_sql_workflow_source_not_established"
