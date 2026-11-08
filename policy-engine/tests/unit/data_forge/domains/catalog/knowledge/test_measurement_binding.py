"""Catalog correspondence requires exact meanings and selected evidence bytes."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts import input_ref_from_artifact_ref
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
)
from polisyos.data_forge.domains.catalog.knowledge.measurement_binding import (
    _AssessmentRefusal,
    _reopen_definition_evidence,
    assess_measurement_to_model_candidate,
)
from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority_model_input_discovery import (
    _put_selected_model_json,
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
            definition_evidence_refs=(SelectedVariableBindingRef.model_validate(evidence.model_dump()),),
        ),
    )


def _representation(store: FileSystemCAS, spec: tuple):
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
    )
    ref = store.put_json(
        representation,
        PutOptions(
            kind=representation.ARTIFACT_KIND,
            media_type=representation.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=representation.ARTIFACT_SCHEMA_NAME,
                version=representation.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(meaning_ref, role="semantic_definition")],
        ),
        return_selected_profile=True,
    )
    return VariableRepresentationRef.model_validate(ref.model_dump())


def _fixture_model_interface(
    store: FileSystemCAS,
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
        key: _representation(store, spec)
        for key, spec in {
            "target": (
                "test.model.tax-rate.ratio", definitions["tax_rate"],
                definitions["tax_liability"], definitions["tax_base"], "parameter",
            ),
            "source_tax": (
                "test.catalog.tax-rate.ratio", definitions["tax_rate"],
                definitions["tax_liability"], definitions["tax_base"], "parameter",
            ),
            "fiscal": (
                "test.catalog.balance-gdp.ratio", definitions["balance_gdp"],
                definitions["balance"], definitions["gdp"], "flow",
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
    )
    profile_ref = _put_selected_model_json(
        store,
        profile,
        kind=profile.ARTIFACT_KIND,
        name=profile.ARTIFACT_SCHEMA_NAME,
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
            population_ref="population:country", geography_ref="UA", jurisdiction_ref="UA",
            period_start=date(2022, 1, 1), period_end=date(2022, 12, 31),
            time_role="observation_time", period_basis="calendar_year",
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

        assert assess(
            tax_projection, tax_row, "tax_rate_definition", "tax_rate_representation"
        ).status == "candidate"
    finally:
        native_owner.overlay.close()
