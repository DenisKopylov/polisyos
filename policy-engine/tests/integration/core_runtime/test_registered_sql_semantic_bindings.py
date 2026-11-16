"""Real registered SQL can enter Foundry only as a scoped candidate input."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
    FileSystemCAS,
    artifact_ref_identity_key,
    load_core_json_artifact,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts.decision_validity import RegisteredSQLAdmissionBinding
from polisyos.core.contracts.foundry import (
    FoundryInputBindingRule,
    FoundryInputBindings,
    FoundryInputBindingsRef,
)
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPortDeclaration,
    load_model_input_obligation,
    load_program_graph_input_interface,
    persist_model_input_port_declaration,
)
from polisyos.core.contracts.semantic_input_binding import (
    ResolvedInputBindingManifest,
    ResolvedMeasurementInput,
    persist_resolved_input_binding_manifest,
)
from polisyos.core.contracts.variable_binding import (
    REGISTERED_SQL_MEASUREMENT_LIMITATIONS,
    RegisteredSQLMeasurementOccurrence,
    SelectedVariableBindingRef,
    load_scoped_measurement_occurrence,
)
from polisyos.core.security import tenant_scope
from polisyos.data_forge import read_api
from polisyos.foundry.data_plane.bindings import (
    build_input_bindings,
    load_input_bindings,
    reconcile_semantic_input_bindings,
)
from polisyos.foundry.execute import load_state_snapshot
from polisyos.runtime.quality.model_input_requirements import (
    verify_program_graph_input_preflight,
)
from tests._helpers.program_graph_tax_subsidy_input import (
    prepare_program_graph_tax_subsidy_input_case,
)
from tests.integration.runtime.http.test_registered_sql_live_grant import (
    CELL,
    TENANT,
    _post,
)  # noqa: F401 - pytest discovers imported fixtures.
from tests.integration.runtime.http.test_registered_sql_live_grant import (
    source_grant_env as source_grant_env,
)
from tests.unit.runtime.quality.test_model_input_requirements import (
    _context,
    _interface,
    _opening_stock_port,
    _preflight,
)


def _calendar_year_stock_declaration(store):
    """Reuse the stock port with its required explicit annual period basis."""
    port = _opening_stock_port(store)
    scoped_port = port.model_copy(
        update={"scope": port.scope.model_copy(update={"period_basis": "calendar_year"})}
    )
    return persist_model_input_port_declaration(
        store,
        ModelInputPortDeclaration(ports=(scoped_port,)),
    )


def _selected_ref(ref: ArtifactRef) -> SelectedVariableBindingRef:
    return SelectedVariableBindingRef.model_validate(ref.model_dump(mode="python"))


def _persist_binding_override(
    store: FileSystemCAS, bindings: FoundryInputBindings
) -> FoundryInputBindingsRef:
    """Persist an adversarial but typed binding with matching direct edges."""
    inputs = [
        input_ref_from_artifact_ref(bindings.data_snapshot_ref, role="input.data_snapshot_ref"),
        input_ref_from_artifact_ref(
            bindings.registry_bundle_ref,
            role="input.registry_bundle_ref",
        ),
        input_ref_from_artifact_ref(
            bindings.bound_state_snapshot_ref,
            role="artifact.bound_state_snapshot_ref",
        ),
    ]
    if bindings.resolved_binding_manifest_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                bindings.resolved_binding_manifest_ref,
                role="input.resolved_binding_manifest_ref",
            )
        )
    if bindings.registered_sql_admission_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                bindings.registered_sql_admission_ref,
                role="input.registered_sql_admission_ref",
            )
        )
    if bindings.quality_report_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                bindings.quality_report_ref,
                role="input.quality_report_ref",
            )
        )
    ref = store.put_json(
        bindings,
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
                version=bindings.schema_version,
            ),
            inputs=inputs,
        ),
        return_selected_profile=True,
    )
    return FoundryInputBindingsRef.model_validate(ref.model_dump(mode="python"))


def _fresh_read_only_reconcile(
    cas_root: Path, bindings_ref: FoundryInputBindingsRef
) -> tuple[str, ...]:
    """Replay one selected binding through a fresh read-only CAS surface."""
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        reader = FileSystemCAS.open_existing_read_only(cas_root)
        assert not hasattr(reader, "put_json")
        bindings = load_input_bindings(reader, bindings_ref)
        return reconcile_semantic_input_bindings(reader, bindings)


@contextmanager
def _withheld(path: Path, backup: Path) -> Iterator[None]:
    """Temporarily remove one selected CAS member and always restore it."""
    assert path.is_file()
    path.rename(backup)
    try:
        yield
    finally:
        backup.rename(path)


def test_real_registered_sql_semantic_binding_is_candidate_only(
    source_grant_env,  # noqa: F811 - pytest injects the imported fixture.
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reopen exact SQL lineage and one initial-state candidate without executing Foundry."""
    import polisyos.foundry.execute.api as execute_api
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.foundry.methods.catalog.mechanism.runtime import TaxSubsidyMechanismMethod

    def unexpected_execution(*_args, **_kwargs):
        pytest.fail("registered_sql_semantic_binding_must_not_execute_foundry")

    monkeypatch.setattr(execute_api, "execute", unexpected_execution)
    monkeypatch.setattr(execute_api, "execute_program_graph", unexpected_execution)
    monkeypatch.setattr(MethodDispatcher, "dispatch", unexpected_execution)
    monkeypatch.setattr(
        TaxSubsidyMechanismMethod,
        "pure_step",
        staticmethod(unexpected_execution),
    )

    _, _, client, source_token, body, _ = source_grant_env
    with sqlite3.connect(tmp_path / "policy.sqlite") as database:
        database.execute("UPDATE policy_inputs SET baseline = scenario WHERE rowid = 1")
        database.execute("DELETE FROM policy_inputs WHERE rowid > 2")

    source_headers = {"Authorization": f"Bearer {source_token}", "X-Tenant-ID": TENANT}
    genesis = client.post(
        "/api/v1/control/registered-sql/registrations",
        headers=source_headers,
        json={"slot_id": "source-a", "event_id": "source-genesis-a"},
    )
    assert genesis.status_code == 200, genesis.text
    admitted_a = _post(
        client,
        source_token,
        {
            **body,
            "event_id": "semantic-source-a",
            "occurrence_id": "semantic-source-a-occurrence",
            "expected_predecessor": genesis.json()["registration"]["event_ref"],
        },
    )
    assert admitted_a.status_code == 200, admitted_a.text
    selected_a = admitted_a.json()
    admitted_i = _post(
        client,
        source_token,
        {
            **body,
            "event_id": "semantic-source-i",
            "occurrence_id": "semantic-source-i-occurrence",
            "expected_predecessor": selected_a["receipt"]["event_ref"],
        },
    )
    assert admitted_i.status_code == 200, admitted_i.text
    selected_i = admitted_i.json()

    store = client.app.state.runtime_container.runtime_api_context.store
    admission_ref_a = ArtifactRef.model_validate(selected_a["binding_ref"])
    admission_ref_i = ArtifactRef.model_validate(selected_i["binding_ref"])
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        admission_a = validate_core_model_json_artifact(
            RegisteredSQLAdmissionBinding, store, admission_ref_a
        )
        admission_i = validate_core_model_json_artifact(
            RegisteredSQLAdmissionBinding, store, admission_ref_i
        )
        payload_ref_a = admission_a.materialization.payload_ref
        payload_ref_i = admission_i.materialization.payload_ref
        payload_bytes = store.get_bytes(payload_ref_a)
        rows = load_core_json_artifact(store, payload_ref_a)
        assert payload_bytes == store.get_bytes(payload_ref_i)
        assert payload_ref_a.artifact_id == payload_ref_i.artifact_id
        assert admission_ref_a.artifact_id != admission_ref_i.artifact_id
        assert admission_a.receipt.event_ref != admission_i.receipt.event_ref
        assert isinstance(rows, list) and isinstance(rows[0], dict)
        assert Decimal(str(rows[0]["baseline"])) == Decimal("11")
        assert Decimal(str(rows[0]["scenario"])) == Decimal("11")

        case = prepare_program_graph_tax_subsidy_input_case(
            tmp_path / "program-graph",
            opening_balance_usd=None,
            model_input_port_declaration_builder=_calendar_year_stock_declaration,
            store=store,
        )
        try:
            assert load_input_bindings(store, case.input_bindings_ref).schema_version == "1.0"
            snapshot_ref = admission_a.materialization.snapshot_ref
            sql_predecessor = build_input_bindings(
                store,
                data_snapshot_ref=snapshot_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                rules=[
                    FoundryInputBindingRule(
                        binding_id="sql-baseline",
                        source_path="baseline",
                        target_slot_id="agents.income",
                    )
                ],
                registered_sql_admission_ref=admission_ref_a,
                return_selected_profile=True,
            )
            predecessor_bindings = load_input_bindings(store, sql_predecessor.input_bindings_ref)
            assert predecessor_bindings.schema_version == "1.1"
            assert tuple(rule.target_slot_id for rule in predecessor_bindings.rules) == (
                "agents.income",
            )
            assert all(
                rule.target_slot_id != "government.balance" for rule in predecessor_bindings.rules
            )

            sql_case = replace(
                case,
                data_snapshot_ref=snapshot_ref,
                input_bindings_ref=sql_predecessor.input_bindings_ref,
                bound_state_snapshot_ref=sql_predecessor.bound_state_snapshot_ref,
            )
            interface_ref = _interface(sql_case)
            interface = load_program_graph_input_interface(store, interface_ref)
            (port,) = tuple(item for item in interface.ports if item.port_id == "opening-stock")
            assert port.purpose == "initial_state"
            assert port.scope.period_basis == "calendar_year"
            preflight = _preflight(
                sql_case,
                interface_ref,
                _context(sql_case),
                steps=(0,),
            )
            selected_preflight = verify_program_graph_input_preflight(
                store,
                obligation_set_ref=preflight.obligation_set_ref,
                expected_invocation=preflight.invocation,
            )
            assert preflight.invocation.steps == (0,)
            assert selected_preflight.supplied_initial_slots == ("agents.income",)
            (obligation_ref,) = selected_preflight.obligation_refs
            obligation = load_model_input_obligation(store, obligation_ref)
            assert obligation.port.port_id == "opening-stock"
            assert obligation.port.purpose == "initial_state"
            assert obligation.port.carrier == "state_path"

            read_limits = CoreJsonReadLimits(
                max_bytes=1_000_000,
                max_depth=8,
                max_elements=10_000,
                max_manifest_bytes=1_000_000,
            )
            before_occurrence_ids = set(map(str, store.iter_artifact_ids()))
            with pytest.raises(
                CoreJsonReadBoundsRefusalError, match=r"^canon_profile_bounded_bytes_exceeded$"
            ):
                read_api.catalog.materialize_registered_sql_measurement_occurrence(
                    store,
                    registered_sql_admission_ref=admission_ref_a,
                    source_path="0.scenario",
                    source_definition_ref=port.semantic_definition_ref,
                    source_representation_ref=port.representation_ref,
                    source_scope=port.scope,
                    declared_release="fixture:source-a:declared-v1",
                    read_limits=replace(read_limits, max_bytes=1),
                )
            assert set(map(str, store.iter_artifact_ids())) == before_occurrence_ids
            occurrence_ref = read_api.catalog.materialize_registered_sql_measurement_occurrence(
                store,
                registered_sql_admission_ref=admission_ref_a,
                source_path="0.scenario",
                source_definition_ref=port.semantic_definition_ref,
                source_representation_ref=port.representation_ref,
                source_scope=port.scope,
                declared_release="fixture:source-a:declared-v1",
                read_limits=read_limits,
            )
            with pytest.raises(ValueError, match=r"^source_profile_required$"):
                read_api.catalog.materialize_registered_sql_measurement_occurrence(
                    store,
                    registered_sql_admission_ref=admission_ref_a.model_copy(
                        update={"manifest_profile_sha256": None}
                    ),
                    source_path="0.scenario",
                    source_definition_ref=port.semantic_definition_ref,
                    source_representation_ref=port.representation_ref,
                    source_scope=port.scope,
                    declared_release="fixture:source-a:declared-v1",
                    read_limits=read_limits,
                )
            correspondence = read_api.catalog.assess_selected_measurement_to_model_candidate(
                store,
                occurrence_ref=occurrence_ref,
                source_definition_ref=port.semantic_definition_ref,
                source_representation_ref=port.representation_ref,
                model_interface_ref=_selected_ref(interface_ref),
                port_id=port.port_id,
            )
            assert correspondence.status == "candidate"
            assert correspondence.semantic_correspondence == "recomputed"
            assert correspondence.correspondence_basis_ref is not None
            assert correspondence.occurrence_ref == occurrence_ref
            assert correspondence.independent_origin == "not_established"
            assert correspondence.source_currentness == "not_established"

            occurrence = load_scoped_measurement_occurrence(store, occurrence_ref)
            assert isinstance(occurrence, RegisteredSQLMeasurementOccurrence)
            assert Decimal(occurrence.canonical_value) == Decimal("11")
            assert occurrence.source_selection.source_path == "0.scenario"
            assert occurrence.source_selection.declared_release == "fixture:source-a:declared-v1"
            assert (
                occurrence.source_selection.authority_purpose == "candidate_simulation_input_only"
            )
            assert occurrence.source_selection.source_meaning_provenance == "consumer_asserted"
            assert occurrence.source_selection.source_release_provenance == "consumer_asserted"
            assert occurrence.source_selection.source_scope_provenance == "consumer_asserted"
            assert occurrence.source_selection.source_scope.period_basis == "calendar_year"
            assert occurrence.source_selection.empirical_correctness == "not_established"
            assert occurrence.source_selection.source_currentness == "not_established"
            assert "empirical_correctness_not_established" in (
                occurrence.source_selection.limitation_codes
            )
            assert "source_currentness_not_established" in (
                occurrence.source_selection.limitation_codes
            )

            (measurement,) = (
                ResolvedMeasurementInput(
                    binding_id="sql-opening-stock",
                    model_input_obligation_ref=_selected_ref(obligation_ref),
                    selected_occurrence_ref=occurrence_ref,
                    correspondence_ref=correspondence.correspondence_basis_ref,
                    source_path="0.scenario",
                ),
            )
            manifest = ResolvedInputBindingManifest(
                schema_version="1.0",
                data_snapshot_ref=_selected_ref(snapshot_ref),
                model_input_obligation_set_ref=_selected_ref(preflight.obligation_set_ref),
                measurements=(measurement,),
                retained_binding_ids=("sql-baseline",),
            )
            assert not manifest.method_input_steps
            assert not manifest.entity_vector_steps
            manifest_ref = persist_resolved_input_binding_manifest(store, manifest)
            semantic_build = build_input_bindings(
                store,
                data_snapshot_ref=snapshot_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                rules=[
                    FoundryInputBindingRule(
                        binding_id="sql-baseline",
                        source_path="baseline",
                        target_slot_id="agents.income",
                    ),
                    FoundryInputBindingRule(
                        binding_id="sql-opening-stock",
                        source_path="0.scenario",
                        target_slot_id="government.balance",
                    ),
                ],
                registered_sql_admission_ref=admission_ref_a,
                resolved_binding_manifest_ref=manifest_ref,
                return_selected_profile=True,
            )
            (tmp_path / "combined-binding-handoff.json").write_text(
                json.dumps(
                    {
                        "cas_root": str(store.root),
                        "input_bindings_ref": semantic_build.input_bindings_ref.model_dump(
                            mode="json"
                        ),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            selected_bindings = load_input_bindings(store, semantic_build.input_bindings_ref)
            assert selected_bindings.schema_version == "1.3"
            assert selected_bindings.registered_sql_admission_ref == admission_ref_a
            assert selected_bindings.resolved_binding_manifest_ref == manifest_ref
            assert selected_bindings.selected_method_inputs is None
            assert selected_bindings.selected_method_input_steps is None
            bound_state = load_state_snapshot(
                store, snapshot_ref=selected_bindings.bound_state_snapshot_ref
            )
            assert Decimal(str(float(bound_state.government_balance))) == Decimal("11")

            positive_notes = _fresh_read_only_reconcile(
                store.root, semantic_build.input_bindings_ref
            )
            assert "semantic_input_use:candidate_simulation_input_only" in positive_notes
            assert {
                "semantic_input_limitation:" + code
                for code in REGISTERED_SQL_MEASUREMENT_LIMITATIONS
            }.issubset(positive_notes)
            report = load_core_json_artifact(store, semantic_build.input_binding_report_ref)
            assert set(REGISTERED_SQL_MEASUREMENT_LIMITATIONS).issubset(report["warnings"])

            wrong_path_manifest = manifest.model_copy(
                update={
                    "measurements": (measurement.model_copy(update={"source_path": "0.baseline"}),)
                }
            )
            wrong_path_manifest_ref = persist_resolved_input_binding_manifest(
                store, wrong_path_manifest
            )
            wrong_path_bindings_ref = _persist_binding_override(
                store,
                selected_bindings.model_copy(
                    update={"resolved_binding_manifest_ref": wrong_path_manifest_ref}
                ),
            )
            with pytest.raises(
                ValueError,
                match=r"^foundry_input_bindings_semantic_sql_source_mismatch$",
            ):
                _fresh_read_only_reconcile(store.root, wrong_path_bindings_ref)

            assert payload_bytes == store.get_bytes(payload_ref_a)
            expected_source_error = (
                "registered_sql_binding_snapshot_mismatch"
                if artifact_ref_identity_key(admission_i.materialization.snapshot_ref)
                != artifact_ref_identity_key(snapshot_ref)
                else "foundry_input_bindings_semantic_sql_source_mismatch"
            )
            wrong_source_bindings_ref = _persist_binding_override(
                store,
                selected_bindings.model_copy(
                    update={"registered_sql_admission_ref": admission_ref_i}
                ),
            )
            with pytest.raises(ValueError, match=f"^{expected_source_error}$"):
                _fresh_read_only_reconcile(store.root, wrong_source_bindings_ref)

            capture_ref = admission_a.materialization.producer_capture_ref
            assert capture_ref.manifest_profile_sha256 is not None
            capture_blob = store._paths(capture_ref.artifact_id)[0]
            payload_blob = store._paths(payload_ref_a.artifact_id)[0]
            capture_profile = store._manifest_path_for_ref(
                capture_ref.artifact_id,
                capture_ref.manifest_profile_sha256,
            )
            for label, selected_path in (
                ("capture-blob", capture_blob),
                ("payload-blob", payload_blob),
                ("capture-profile", capture_profile),
            ):
                backup = tmp_path / f"withheld-{label}"
                expected_refusal = (
                    "DataSnapshot owner-lineage child ref is unverified"
                    if label == "payload-blob"
                    else "selected_occurrence_source_replay_failed"
                )
                with (
                    _withheld(selected_path, backup),
                    pytest.raises(ValueError, match=f"^{expected_refusal}$") as missing,
                ):
                    _fresh_read_only_reconcile(store.root, semantic_build.input_bindings_ref)
                if label == "payload-blob":
                    cause = missing.value.__cause__
                    assert isinstance(cause, FileNotFoundError)
                    assert cause.filename is not None
                    assert Path(cause.filename) == selected_path
                assert (
                    _fresh_read_only_reconcile(store.root, semantic_build.input_bindings_ref)
                    == positive_notes
                )

            admission_inputs = store.get_manifest(admission_ref_a).inputs
            assert any(edge.role == "source.capture" for edge in admission_inputs)
            admission_without_capture_role = store.put_json(
                admission_a,
                PutOptions(
                    kind=RegisteredSQLAdmissionBinding.ARTIFACT_KIND,
                    media_type=RegisteredSQLAdmissionBinding.ARTIFACT_MEDIA_TYPE,
                    schema=SchemaInfo(
                        name=RegisteredSQLAdmissionBinding.ARTIFACT_SCHEMA_NAME,
                        version=RegisteredSQLAdmissionBinding.ARTIFACT_SCHEMA_VERSION,
                    ),
                    inputs=[edge for edge in admission_inputs if edge.role != "source.capture"],
                ),
                return_selected_profile=True,
            )
            assert all(
                edge.role != "source.capture"
                for edge in store.get_manifest(admission_without_capture_role).inputs
            )
            missing_role_bindings_ref = _persist_binding_override(
                store,
                selected_bindings.model_copy(
                    update={"registered_sql_admission_ref": admission_without_capture_role}
                ),
            )
            with pytest.raises(
                ValueError,
                match=r"^registered_sql_binding_edges_not_established$",
            ):
                _fresh_read_only_reconcile(store.root, missing_role_bindings_ref)
            assert (
                _fresh_read_only_reconcile(store.root, semantic_build.input_bindings_ref)
                == positive_notes
            )

            # A large actual captured view is legal SQL transport. This bounded
            # candidate reader must refuse it before emitting an occurrence,
            # even if the caller supplies a larger JSON budget.
            with sqlite3.connect(tmp_path / "policy.sqlite") as database:
                database.execute(
                    "UPDATE policy_inputs SET note = ? WHERE rowid = 1", ("x" * (5 * 1024 * 1024),)
                )
            oversized_response = _post(
                client,
                source_token,
                {
                    **body,
                    "event_id": "semantic-source-oversized",
                    "occurrence_id": "semantic-source-oversized-occurrence",
                    "expected_predecessor": selected_i["receipt"]["event_ref"],
                },
            )
            assert oversized_response.status_code == 200, oversized_response.text
            oversized_ref = ArtifactRef.model_validate(oversized_response.json()["binding_ref"])
            before_oversized_ids = set(map(str, store.iter_artifact_ids()))
            with pytest.raises(
                CoreJsonReadBoundsRefusalError, match=r"^canon_profile_bounded_bytes_exceeded$"
            ):
                read_api.catalog.materialize_registered_sql_measurement_occurrence(
                    store,
                    registered_sql_admission_ref=oversized_ref,
                    source_path="0.scenario",
                    source_definition_ref=port.semantic_definition_ref,
                    source_representation_ref=port.representation_ref,
                    source_scope=port.scope,
                    declared_release="fixture:source-oversized:declared-v1",
                    read_limits=CoreJsonReadLimits(
                        max_bytes=8 * 1024 * 1024,
                        max_depth=32,
                        max_elements=200_000,
                        max_manifest_bytes=1024 * 1024,
                    ),
                )
            assert set(map(str, store.iter_artifact_ids())) == before_oversized_ids
        finally:
            case.close()
