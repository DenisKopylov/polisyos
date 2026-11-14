"""Catalog correspondence requires exact meanings and selected evidence bytes."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
)
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.epoch import load_verified_epoch_statement
from polisyos.core.contracts.foundry import ExecPlanRef, ProgramGraphRef
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPort,
    ModelInputScope,
    ProgramGraphInputInterface,
    persist_program_graph_input_interface,
)
from polisyos.core.contracts.variable_binding import (
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    SelectedVariableBindingRef,
    VariableRepresentation,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    load_variable_representation,
    variable_representation_manifest_inputs,
)
from polisyos.data_forge.domains.catalog.knowledge.measurement_binding import (
    _AssessmentRefusal,
    _reopen_definition_evidence,
    assess_measurement_to_model_candidate,
)
from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority_model_input_discovery import (
    _put_semantic_definition,
)


def _definition(store: FileSystemCAS, namespace: str, stable_id: str, meaning: str):
    evidence = store.put_bytes(
        f"Test-owned meaning: {meaning}\n".encode(),
        PutOptions(kind="test.semantic_definition_evidence", media_type="text/plain"),
        return_selected_profile=True,
    )
    return _put_semantic_definition(
        store,
        VariableSemanticDefinition(
            namespace=namespace,
            stable_id=stable_id,
            revision="fixture-r1",
            meaning=meaning,
            definition_evidence_refs=(
                SelectedVariableBindingRef.model_validate(evidence.model_dump()),
            ),
        ),
    )


def _representation(
    store: FileSystemCAS,
    spec: tuple,
    *,
    methodology_ref: SelectedVariableBindingRef | None = None,
):
    representation_id, meaning_ref, numerator_ref, denominator_ref, quantity_kind = spec
    representation = VariableRepresentation(
        representation_id=representation_id,
        revision="fixture-r1",
        semantic_definition_ref=meaning_ref,
        quantity_kind=quantity_kind,
        measure_form="rate",
        unit_id="ratio",
        scale_to_unit=Decimal("1"),
        numerator_ref=numerator_ref,
        denominator_ref=denominator_ref,
        time_support="period_rate",
        temporal_granularity="annual",
        aggregation="mean",
        grain=("jurisdiction", "period"),
        population_ref="population:country",
        **(
            {
                "schema_version": "polisyos.catalog.variable_representation.v2",
                "methodology_ref": methodology_ref,
            }
            if methodology_ref is not None
            else {}
        ),
    )
    ref = store.put_json(
        representation,
        PutOptions(
            kind=representation.ARTIFACT_KIND,
            media_type=representation.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=representation.ARTIFACT_SCHEMA_NAME,
                version="2.0" if methodology_ref is not None else "1.0",
            ),
            inputs=list(variable_representation_manifest_inputs(representation)),
        ),
        return_selected_profile=True,
    )
    return VariableRepresentationRef.model_validate(ref.model_dump())


def _fixture_model_interface(
    store: FileSystemCAS,
    *,
    methodology_ref: SelectedVariableBindingRef | None = None,
) -> tuple[SelectedVariableBindingRef, dict[str, ArtifactRef]]:
    definitions = {
        key: _definition(store, namespace, stable_id, meaning)
        for key, namespace, stable_id, meaning in (
            ("tax_rate", "test.policy", "income_tax_rate", "Tax liability / taxable income."),
            ("tax_liability", "test.policy", "income_tax_liability", "Personal tax liability."),
            ("tax_base", "test.policy", "taxable_personal_income", "Taxable personal income."),
            ("balance_gdp", "test.fiscal", "balance_to_gdp", "Government fiscal balance / GDP."),
            ("balance", "test.fiscal", "government_balance_flow", "Government fiscal flow."),
            ("gdp", "test.economy", "nominal_gdp_flow", "Economy-wide nominal GDP flow."),
        )
    }
    representations = {
        key: _representation(store, spec, methodology_ref=methodology_ref)
        for key, spec in {
            "target": (
                "test.model.tax-rate.ratio",
                definitions["tax_rate"],
                definitions["tax_liability"],
                definitions["tax_base"],
                "parameter",
            ),
            "source_tax": (
                "test.catalog.tax-rate.ratio",
                definitions["tax_rate"],
                definitions["tax_liability"],
                definitions["tax_base"],
                "parameter",
            ),
            "fiscal": (
                "test.catalog.balance-gdp.ratio",
                definitions["balance_gdp"],
                definitions["balance"],
                definitions["gdp"],
                "flow",
            ),
        }.items()
    }
    profile = MeasurementBindingProfile(
        profile_id="test.tax-rate.percent-ratio",
        revision="fixture-r1",
        required_axes=(
            MeasurementAxis.QUANTITY_KIND,
            MeasurementAxis.MEASURE_FORM,
            MeasurementAxis.UNIT_ID,
            MeasurementAxis.NUMERATOR_REF,
            MeasurementAxis.DENOMINATOR_REF,
            MeasurementAxis.TIME_SUPPORT,
            MeasurementAxis.TEMPORAL_GRANULARITY,
            MeasurementAxis.AGGREGATION,
            MeasurementAxis.GRAIN,
            MeasurementAxis.POPULATION_REF,
        ),
        **(
            {
                "schema_version": "polisyos.catalog.measurement_binding_profile.v2",
                "optional_axes": (MeasurementAxis.METHODOLOGY_REF,),
            }
            if methodology_ref is not None
            else {}
        ),
    )
    profile_ref = store.put_json(
        profile,
        PutOptions(
            kind=profile.ARTIFACT_KIND,
            media_type=profile.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=profile.ARTIFACT_SCHEMA_NAME,
                version="2.0" if methodology_ref is not None else "1.0",
            ),
        ),
        return_selected_profile=True,
    )
    port = ModelInputPort(
        port_id="income-tax-rate",
        slot_id="global.tax_rate",
        state_path="tax_rate",
        unit_id="ratio",
        purpose="outcome_validation",
        semantic_definition_ref=definitions["tax_rate"],
        representation_ref=representations["target"],
        binding_profile_ref=MeasurementBindingProfileRef.model_validate(profile_ref.model_dump()),
        scope=ModelInputScope(
            population_ref="population:country",
            geography_ref="UA",
            jurisdiction_ref="UA",
            period_start=date(2022, 1, 1),
            period_end=date(2022, 12, 31),
            time_role="observation_time",
            period_basis="calendar_year",
        ),
    )
    selected_refs = {
        kind: store.put_bytes(
            f"selected {kind}".encode(),
            PutOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )
        for kind in ("foundry.program_graph", "foundry.exec_plan", "core.registry_bundle")
    }
    interface_ref = persist_program_graph_input_interface(
        store,
        ProgramGraphInputInterface(
            program_graph_ref=ProgramGraphRef.model_validate(
                selected_refs["foundry.program_graph"].model_dump()
            ),
            exec_plan_ref=ExecPlanRef.model_validate(
                selected_refs["foundry.exec_plan"].model_dump()
            ),
            registry_bundle_ref=selected_refs["core.registry_bundle"],
            ports=(port,),
        ),
    )
    return SelectedVariableBindingRef.model_validate(interface_ref.model_dump()), {
        "tax_rate_definition": definitions["tax_rate"],
        "tax_rate_representation": representations["source_tax"],
        "fiscal_definition": definitions["balance_gdp"],
        "fiscal_representation": representations["fiscal"],
    }


def _definition_with_selected_evidence(
    store: FileSystemCAS,
) -> tuple[VariableSemanticDefinition, SelectedVariableBindingRef]:
    evidence = store.put_bytes(
        b"Meaning: a bounded test-owned semantic definition.\n",
        PutOptions(kind="test.semantic_definition_evidence", media_type="text/plain"),
        return_selected_profile=True,
    )
    evidence_ref = SelectedVariableBindingRef.model_validate(evidence.model_dump(mode="json"))
    return (
        VariableSemanticDefinition(
            namespace="test",
            stable_id="measurement",
            revision="1",
            meaning="A test-owned semantic meaning.",
            definition_evidence_refs=(evidence_ref,),
        ),
        evidence_ref,
    )


def test_catalog_reopens_content_bound_definition_evidence(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition, _ = _definition_with_selected_evidence(store)

    _reopen_definition_evidence(store, definition)


def test_catalog_refuses_when_selected_definition_evidence_bytes_are_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition, selected_ref = _definition_with_selected_evidence(store)

    def missing_selected_bytes(ref):
        if ref.artifact_id == selected_ref.artifact_id:
            raise FileNotFoundError("removed selected source documentation bytes")
        return store.get_bytes(ref)

    monkeypatch.setattr(store, "get_bytes", missing_selected_bytes)

    with pytest.raises(_AssessmentRefusal, match="evidence_bytes_unavailable"):
        _reopen_definition_evidence(store, definition)


def test_native_catalog_ratio_candidate_distinguishes_tax_rate_from_fiscal_balance_to_gdp(
    tmp_path: Path,
) -> None:
    """Check Catalog-only correspondence; this is not compiled tax-rate input or Gate A."""
    store = FileSystemCAS(tmp_path / "cas")
    interface_ref, selected_refs = _fixture_model_interface(store)
    fields = (
        ("test.policy.income_tax_rate", "tax_rate_percent", 0.0, 100.0),
        ("test.fiscal.balance_to_gdp", "fiscal_balance_percent_gdp", -100.0, 100.0),
    )
    native_owner = make_native_multivariable_active_projections(
        tmp_path / "native-catalog",
        source_rows=[
            {
                "country_code": "UA",
                "year": 2022,
                "tax_rate_percent": 20.0,
                "fiscal_balance_percent_gdp": 20.0,
                "condition_json": json.dumps(
                    {
                        "population_ref": "population:country",
                        "geography_ref": "UA",
                        "jurisdiction_ref": "UA",
                        "time_period_basis": "calendar_year",
                    },
                    sort_keys=True,
                ),
            }
        ],
        variable_specs=tuple(
            {
                "target_variable": target,
                "raw_field": field,
                "raw_unit": "percent",
                "canonical_unit": "ratio",
                "unit_transform": "fixed_multiplicative",
                "unit_transform_ref": "fabric://units/fixed-multiplicative/v1",
                "valid_min": low,
                "valid_max": high,
            }
            for target, field, low, high in fields
        ),
        condition_units_by_raw_field={field: "percent" for _, field, _, _ in fields},
        artifact_store=store,
        return_selected_raw_profile=True,
    )
    try:
        tax_projection = native_owner.projections["test.policy.income_tax_rate"]
        fiscal_projection = native_owner.projections["test.fiscal.balance_to_gdp"]
        (tax_row,) = tax_projection.observations
        (fiscal_row,) = fiscal_projection.observations
        for observation in (tax_row.observation, fiscal_row.observation):
            assert float(observation.value) == pytest.approx(0.2)
            assert observation.unit_transform_evidence is not None
            assert observation.unit_transform_evidence.raw_unit == "percent"
            assert observation.unit_transform_evidence.canonical_unit == "ratio"
            assert observation.unit_transform_evidence.multiplier == "0.01"
        assert json.loads(tax_row.observation.condition_json) == json.loads(
            fiscal_row.observation.condition_json
        )
        assert (tax_row.observation.country_code, tax_row.observation.year) == (
            fiscal_row.observation.country_code,
            fiscal_row.observation.year,
        )

        def assess(projection, row, definition_key: str, representation_key: str):
            passport = AdmissionPassport.model_validate(
                load_verified_epoch_statement(
                    store=store,
                    ref=projection.passport_ref,
                    expected_kind="epoch.acquisition_passport_snapshot",
                )
            )
            return assess_measurement_to_model_candidate(
                store,
                native_owner.overlay,
                receipt_ref=projection.receipt_ref,
                passport=passport,
                authority=native_owner.authority,
                observation_id=row.observation.observation_id,
                source_definition_ref=selected_refs[definition_key],
                source_representation_ref=selected_refs[representation_key],
                model_interface_ref=interface_ref,
                port_id="income-tax-rate",
            )

        tax_candidate = assess(
            tax_projection, tax_row, "tax_rate_definition", "tax_rate_representation"
        )
        assert tax_candidate.status == "candidate", tax_candidate.refusal_codes
        assert tax_candidate.semantic_correspondence == "recomputed"
        assert tax_candidate.independent_origin == "not_established"
        assert tax_candidate.source_currentness == "not_established"
        assert "external_empirical_origin_not_established" in tax_candidate.limitation_codes

        fiscal_negative = assess(
            fiscal_projection, fiscal_row, "fiscal_definition", "fiscal_representation"
        )
        assert fiscal_negative.status == "refused"
        assert fiscal_negative.semantic_correspondence == "not_established"
        assert "same_definition_profile_requires_exact_definition" in (
            fiscal_negative.refusal_codes
        )
        assert fiscal_negative.correspondence_basis_ref is None

        assert (
            assess(tax_projection, tax_row, "tax_rate_definition", "tax_rate_representation").status
            == "candidate"
        )
    finally:
        native_owner.overlay.close()


def _fresh_correspondence_result(store: FileSystemCAS, basis_ref: ArtifactRef) -> dict:
    """Replay a persisted Catalog basis offline, without current-use permission."""
    code = """
import sys
from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts import load_program_graph_input_interface
from polisyos.core.contracts.epoch import load_verified_epoch_statement
from polisyos.core.contracts.variable_binding import (
    MeasurementBindingProfile, ScopedCorrespondenceBasis, ScopedCorrespondenceBasisRef,
    ScopedMeasurementOccurrence, VariableSemanticDefinition,
    evaluate_scoped_correspondence_basis, load_variable_representation,
    replay_scoped_measurement_occurrence, scoped_source_selection_from_passport_mapping,
)
from polisyos.data_forge.read_api import catalog as catalog_read_api
store = FileSystemCAS(sys.argv[1])
ref = ScopedCorrespondenceBasisRef.model_validate_json(sys.argv[2])
basis = validate_core_model_json_artifact(ScopedCorrespondenceBasis, store, ref)
occurrence = validate_core_model_json_artifact(
    ScopedMeasurementOccurrence, store, basis.occurrence_ref,
)
passport = load_verified_epoch_statement(
    store=store, ref=occurrence.source_passport_ref,
    expected_kind="epoch.acquisition_passport_snapshot",
)
source = scoped_source_selection_from_passport_mapping(
    passport, source_receipt_ref=occurrence.source_receipt_ref,
    source_passport_ref=occurrence.source_passport_ref,
    source_boundary_candidate_ref=occurrence.source_boundary_candidate_ref,
    source_record_ref=occurrence.source_record_ref,
)
replayed = replay_scoped_measurement_occurrence(
    catalog_read_api.read_scoped_measurement_source_body(
        store, passport_mapping=passport, source_selection=source,
    ), observation_id=occurrence.observation_id,
    source_selection=source, unit_transform_evidence=occurrence.unit_transform_evidence,
)
interface = load_program_graph_input_interface(store, basis.model_interface_ref)
ports = [port for port in interface.ports if port.port_id == basis.model_port_id]
assert len(ports) == 1
result = evaluate_scoped_correspondence_basis(
    basis=basis, occurrence_ref=basis.occurrence_ref, occurrence=occurrence,
    replayed_occurrence=replayed, source_selection=source,
    source_definition_ref=basis.source_definition_ref,
    source_definition=validate_core_model_json_artifact(
        VariableSemanticDefinition, store, basis.source_definition_ref,
    ),
    source_representation_ref=basis.source_representation_ref,
    source_representation=load_variable_representation(store, basis.source_representation_ref),
    target_definition_ref=basis.target_definition_ref,
    target_definition=validate_core_model_json_artifact(
        VariableSemanticDefinition, store, basis.target_definition_ref,
    ),
    target_representation_ref=basis.target_representation_ref,
    target_representation=load_variable_representation(store, basis.target_representation_ref),
    binding_profile_ref=basis.binding_profile_ref,
    profile=validate_core_model_json_artifact(MeasurementBindingProfile, store, basis.binding_profile_ref),
    model_interface_ref=basis.model_interface_ref, model_port=ports[0],
)
print(result.model_dump_json())
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(store.root), basis_ref.model_dump_json()],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return json.loads(result.stdout)


def test_live_scoped_measurement_replays_in_a_fresh_reader_and_refuses_removed_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The admitted source, selected scope and model binding meet in real CAS."""
    from polisyos.core.artifacts import (
        artifact_ref_identity_key,
        validate_core_model_json_artifact,
    )
    from polisyos.core.contracts.variable_binding import (
        ScopedMeasurementOccurrence,
        scoped_measurement_occurrence_manifest_inputs,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import OverlayAdmissionError
    from polisyos.data_forge.read_api import catalog as catalog_read_api
    from tests._helpers.lane01_wdi_profiles import CandidateWDIProfile
    from tests._helpers.semantic_epoch_native import make_native_live_measurement_history
    from tests.integration.runtime_quality.test_program_graph_held_out_fund_binding import (
        _fund_port,
    )
    from tests.unit.runtime.quality.test_model_input_requirements import _opening_stock_port

    store = FileSystemCAS(tmp_path / "cas")
    port = _fund_port(store, _opening_stock_port(store), fund="treasury")
    graph_refs = {
        kind: store.put_bytes(
            f"selected {kind}".encode(),
            PutOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )
        for kind in ("foundry.program_graph", "foundry.exec_plan", "core.registry_bundle")
    }
    interface_ref = SelectedVariableBindingRef.model_validate(
        persist_program_graph_input_interface(
            store,
            ProgramGraphInputInterface(
                program_graph_ref=ProgramGraphRef.model_validate(
                    graph_refs["foundry.program_graph"].model_dump()
                ),
                exec_plan_ref=ExecPlanRef.model_validate(
                    graph_refs["foundry.exec_plan"].model_dump()
                ),
                registry_bundle_ref=graph_refs["core.registry_bundle"],
                ports=(port,),
            ),
        ).model_dump()
    )
    profile = CandidateWDIProfile(
        construct="test.treasury.opening-cash",
        indicator_id="POLICYOS.FIXTURE.TREASURY.STOCK",
        source_title="Test-owned annual treasury stock (current US$)",
        source_description="Controlled test values; external empirical origin is not established.",
        target_slot="test.treasury.opening-cash",
        raw_unit="usd",
        canonical_unit="usd",
        transform="identity",
        transform_ref="fabric://units/usd-identity/v1",
        population="population:treasury",
        fixture_value=640.0,
        source_provenance_class="observed",
        valid_min=0.0,
        valid_max=10_000.0,
        country_code="UKR",
        country_id="UA",
        year=2022,
    )
    history = make_native_live_measurement_history(
        tmp_path / "source",
        profile=profile,
        semantic_definition_ref=port.semantic_definition_ref,
        representation_ref=port.representation_ref,
        attempt_ids=("scoped-source-a",),
        artifact_store=store,
        monkeypatch=monkeypatch,
        source_measure_scope={
            "population": "population:treasury",
            "temporal_granularity": "annual",
            "source_geography_id": "UA",
            "geography_ref": "UA",
            "jurisdiction_ref": "UA",
            "time_period_basis": "calendar_year",
        },
    )
    try:
        active = history.admit(640.0)
        projection = active.projections[history.entry.target_variable]
        (row,) = projection.observations
        assert row.observation.value == 640.0

        occurrence_ref = catalog_read_api.materialize_activated_measurement_occurrence(
            store,
            history.overlay,
            receipt_ref=projection.receipt_ref,
            passport=active.passport,
            authority=history.authority,
            observation_id=row.observation.observation_id,
        )
        assert occurrence_ref.manifest_profile_sha256 is not None
        occurrence = validate_core_model_json_artifact(
            ScopedMeasurementOccurrence, store, occurrence_ref
        )
        assert occurrence.observation_id == row.observation.observation_id
        assert occurrence.canonical_value == str(row.observation.value)
        assert occurrence.year == 2022
        assert occurrence.source_scope.geography_ref == "UA"
        assert occurrence.source_scope.jurisdiction_ref == "UA"
        assert artifact_ref_identity_key(occurrence.source_receipt_ref) == (
            artifact_ref_identity_key(projection.receipt_ref)
        )

        fresh_store = FileSystemCAS(store.root)
        stored_occurrence, replayed_occurrence, source_selection = (
            catalog_read_api.replay_selected_scoped_measurement_facts(
                fresh_store, occurrence_ref
            )
        )
        assert stored_occurrence == occurrence == replayed_occurrence
        assert source_selection.source_receipt_ref == occurrence.source_receipt_ref
        assert source_selection.source_passport_ref == occurrence.source_passport_ref
        assert (
            source_selection.source_boundary_candidate_ref
            == occurrence.source_boundary_candidate_ref
        )
        assert source_selection.source_record_ref == occurrence.source_record_ref
        assert tuple(fresh_store.get_manifest(occurrence_ref).inputs) == (
            scoped_measurement_occurrence_manifest_inputs(occurrence)
        )

        raw_ref = active.evidence.raw_artifact_ref
        assert raw_ref is not None
        actual_get = store.get_bytes

        def missing_raw(ref):
            if isinstance(ref, ArtifactRef) and artifact_ref_identity_key(
                ref
            ) == artifact_ref_identity_key(raw_ref):
                raise FileNotFoundError("test removed the selected raw source")
            return actual_get(ref)

        with monkeypatch.context() as context:
            context.setattr(store, "get_bytes", missing_raw)
            with pytest.raises(_AssessmentRefusal):
                catalog_read_api.replay_selected_scoped_measurement_facts(
                    store, occurrence_ref
                )
            with pytest.raises(OverlayAdmissionError):
                catalog_read_api.materialize_activated_measurement_occurrence(
                    store,
                    history.overlay,
                    receipt_ref=projection.receipt_ref,
                    passport=active.passport,
                    authority=history.authority,
                    observation_id=row.observation.observation_id,
                )

        def assess():
            return assess_measurement_to_model_candidate(
                store,
                history.overlay,
                receipt_ref=projection.receipt_ref,
                passport=active.passport,
                authority=history.authority,
                observation_id=row.observation.observation_id,
                source_definition_ref=port.semantic_definition_ref,
                source_representation_ref=port.representation_ref,
                model_interface_ref=interface_ref,
                port_id=port.port_id,
            )

        result = assess()
        assert result.status == "candidate", result.refusal_codes
        assert result.correspondence_basis_ref is not None
        assert result.independent_origin == result.source_currentness == "not_established"
        fresh = _fresh_correspondence_result(store, result.correspondence_basis_ref)
        assert fresh["status"] == "candidate", fresh
        assert fresh["semantic_correspondence"] == "recomputed"

        raw_ref = active.evidence.raw_artifact_ref
        assert raw_ref is not None
        actual_get = store.get_bytes

        def missing_raw(ref):
            if isinstance(ref, ArtifactRef) and artifact_ref_identity_key(
                ref
            ) == artifact_ref_identity_key(raw_ref):
                raise FileNotFoundError("test removed the selected raw source")
            return actual_get(ref)

        with monkeypatch.context() as context:
            context.setattr(store, "get_bytes", missing_raw)
            refused = assess()
            assert refused.status == "refused"
            assert refused.refusal_codes == ("source_activation_live_source_execution_unresolved",)
        assert assess().status == "candidate"
    finally:
        history.overlay.close()


def test_native_catalog_optional_methodology_is_limited_while_required_denominator_still_refuses(
    tmp_path: Path,
) -> None:
    """Exercise V05 through admitted source, selected artifacts and a fresh basis reader."""
    from polisyos.fabric.docs.ingestion import ingest_doc_bytes
    from polisyos.fabric.docs.types import DocSourceSpec

    store = FileSystemCAS(tmp_path / "cas")
    document = ingest_doc_bytes(
        cas=store,
        fact_log_root=tmp_path / "methodology-facts",
        source=DocSourceSpec(
            source_locator="repo://test/measurement-protocol/r1",
            license="test-owned",
        ),
        raw_bytes=b"Test-owned measurement protocol. Empirical validity is not established.\n",
        mime="text/plain",
    )
    document_manifest = store.get_manifest(document.raw_ref)
    methodology_ref = SelectedVariableBindingRef(
        artifact_id=document_manifest.artifact_id,
        kind=document_manifest.kind,
        media_type=document_manifest.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(document_manifest),
    )
    interface_ref, selected = _fixture_model_interface(store, methodology_ref=methodology_ref)
    original_ref = VariableRepresentationRef.model_validate(
        selected["tax_rate_representation"].model_dump()
    )
    original = load_variable_representation(store, original_ref)
    native_owner = make_native_multivariable_active_projections(
        tmp_path / "native-catalog",
        source_rows=[
            {
                "country_code": "UA",
                "year": 2022,
                "rate_pct": 20.0,
                "condition_json": json.dumps(
                    {
                        "population_ref": "population:country",
                        "geography_ref": "UA",
                        "jurisdiction_ref": "UA",
                        "time_period_basis": "calendar_year",
                    },
                    sort_keys=True,
                ),
            }
        ],
        variable_specs=(
            {
                "target_variable": "test.policy.income_tax_rate",
                "raw_field": "rate_pct",
                "raw_unit": "percent",
                "canonical_unit": "ratio",
                "unit_transform": "fixed_multiplicative",
                "unit_transform_ref": "fabric://units/fixed-multiplicative/v1",
                "valid_min": 0.0,
                "valid_max": 100.0,
            },
        ),
        condition_units_by_raw_field={"rate_pct": "percent"},
        artifact_store=store,
        return_selected_raw_profile=True,
    )
    try:
        projection = native_owner.projections["test.policy.income_tax_rate"]
        (row,) = projection.observations
        passport = AdmissionPassport.model_validate(
            load_verified_epoch_statement(
                store=store,
                ref=projection.passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
        )

        def persist(value: VariableRepresentation) -> VariableRepresentationRef:
            return VariableRepresentationRef.model_validate(
                store.put_json(
                    value,
                    PutOptions(
                        kind=value.ARTIFACT_KIND,
                        media_type=value.ARTIFACT_MEDIA_TYPE,
                        schema=SchemaInfo(name=value.ARTIFACT_SCHEMA_NAME, version="2.0"),
                        inputs=list(variable_representation_manifest_inputs(value)),
                    ),
                    return_selected_profile=True,
                ).model_dump()
            )

        def assess(representation_ref: VariableRepresentationRef):
            return assess_measurement_to_model_candidate(
                store,
                native_owner.overlay,
                receipt_ref=projection.receipt_ref,
                passport=passport,
                authority=native_owner.authority,
                observation_id=row.observation.observation_id,
                source_definition_ref=selected["tax_rate_definition"],
                source_representation_ref=representation_ref,
                model_interface_ref=interface_ref,
                port_id="income-tax-rate",
            )

        positive = assess(original_ref)
        assert positive.status == "candidate", positive.refusal_codes
        assert MeasurementAxis.METHODOLOGY_REF in positive.recomputed_axes
        assert positive.optional_unknown_axes == ()
        assert positive.independent_origin == positive.source_currentness == "not_established"

        missing_method_ref = persist(original.model_copy(update={"methodology_ref": None}))
        limited = assess(missing_method_ref)
        assert limited.status == "candidate", limited.refusal_codes
        assert limited.optional_unknown_axes == (MeasurementAxis.METHODOLOGY_REF,)
        assert "optional_axis_unknown:methodology_ref" in limited.limitation_codes
        assert limited.independent_origin == limited.source_currentness == "not_established"
        assert limited.correspondence_basis_ref is not None
        fresh = _fresh_correspondence_result(store, limited.correspondence_basis_ref)
        assert fresh["status"] == "candidate"
        assert fresh["optional_unknown_axes"] == ["methodology_ref"]
        assert "optional_axis_unknown:methodology_ref" in fresh["limitation_codes"]
        assert "external_empirical_origin_not_established" in fresh["limitation_codes"]

        for denominator in (
            None,
            _definition(store, "test.economy", "other_gdp_flow", "A different GDP denominator."),
            _definition(
                store, "test.fiscal", "other_revenue_flow", "A different revenue denominator."
            ),
        ):
            wrong_ref = persist(original.model_copy(update={"denominator_ref": denominator}))
            refused = assess(wrong_ref)
            assert refused.status == "refused"
            assert refused.semantic_correspondence == "not_established"
            expected = "unknown" if denominator is None else "mismatch"
            assert f"required_axis_{expected}:denominator_ref" in refused.refusal_codes
            assert refused.correspondence_basis_ref is None

        document_path, _ = store._paths(methodology_ref.artifact_id)
        original_bytes = document_path.read_bytes()
        document_path.write_bytes(b"X" + original_bytes[1:])
        try:
            refused = assess(original_ref)
            assert refused.status == "refused"
            assert refused.refusal_codes == ("selected_owner_input_invalid",)
            assert refused.correspondence_basis_ref is None
        finally:
            document_path.write_bytes(original_bytes)
        assert assess(original_ref).status == "candidate"
    finally:
        native_owner.overlay.close()
