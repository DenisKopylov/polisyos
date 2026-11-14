"""The bounded derived relation joins roles, rather than labels or units alone."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    FoundryInputBindingsRef,
    ProgramGraphRef,
    StateSnapshotRef,
)
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    ModelInputObligation,
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ProgramGraphInputDependency,
)
from polisyos.core.contracts.semantic_derived_binding import (
    DerivedInputCorrespondenceBasis,
    DerivedInputProfile,
    DerivedMeasurementRole,
    RatioDenominatorSourceContext,
    ReplayedDerivedMeasurementRole,
    evaluate_derived_input_correspondence,
    load_derived_input_correspondence,
    persist_derived_input_correspondence,
    persist_derived_input_profile,
    persist_ratio_denominator_source_context,
)
from polisyos.core.contracts.variable_binding import (
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    ModelInputScope,
    ScopedMeasurementOccurrence,
    ScopedMeasurementOccurrenceRef,
    ScopedSourceSelection,
    SelectedVariableBindingRef,
    VariableRepresentation,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
    variable_representation_manifest_inputs,
)
from polisyos.core.derivations import (
    AuthorityProjection,
    BasisSignature,
    SourceSeries,
    TransformFamily,
    TransformFamilyRegistry,
    build_derivation_recipe,
    materialize_derivation,
    persist_derivation_recipe_artifact,
    persist_source_series,
    persist_transform_family_registry,
)
from polisyos.ir.kernel.units import DEFAULT_UNITS_REGISTRY, MoneyUnit


def _selected(store: FileSystemCAS, ref: ArtifactRef) -> SelectedVariableBindingRef:
    return SelectedVariableBindingRef.model_validate(
        ref.model_dump()
        | {"manifest_profile_sha256": artifact_manifest_profile_sha256(store.get_manifest(ref))}
    )


def _put_contract(store: FileSystemCAS, value, *, version="1.0", inputs=()):
    return _selected(
        store,
        store.put_json(
            value,
            PutOptions(
                kind=value.ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(name=value.ARTIFACT_SCHEMA_NAME, version=version),
                inputs=list(inputs),
            ),
            return_selected_profile=True,
        ),
    )


def _definition(store: FileSystemCAS, stable_id: str):
    evidence = _selected(
        store,
        store.put_bytes(
            f"Explicit bounded fixture definition: {stable_id}".encode(),
            PutOptions(kind="fixture.semantic_definition", media_type="text/plain"),
        ),
    )
    value = VariableSemanticDefinition(
        namespace="fixture",
        stable_id=stable_id,
        revision="1",
        meaning=f"Explicitly declared fixture meaning for {stable_id}.",
        definition_evidence_refs=(evidence,),
    )
    ref = VariableSemanticDefinitionRef.model_validate(
        _put_contract(
            store,
            value,
            inputs=(input_ref_from_artifact_ref(evidence, role="definition_evidence"),),
        ).model_dump()
    )
    return ref, value


def _representation(
    store: FileSystemCAS,
    definition_ref: VariableSemanticDefinitionRef,
    *,
    population: str,
    money: MoneyUnit,
    numerator_ref=None,
    denominator_ref=None,
):
    value = VariableRepresentation(
        schema_version="polisyos.catalog.variable_representation.v3",
        representation_id="fixture." + definition_ref.artifact_id.hex,
        revision="1",
        semantic_definition_ref=definition_ref,
        quantity_kind="flow",
        measure_form="ratio" if denominator_ref is not None else "absolute",
        unit_id="ratio" if denominator_ref is not None else "usd",
        scale_to_unit=Decimal("1"),
        numerator_ref=numerator_ref,
        denominator_ref=denominator_ref,
        time_support="period_total",
        temporal_granularity="annual",
        aggregation="identity",
        grain=("aggregate_community", "period"),
        population_ref=population,
        money_unit=money,
    )
    ref = VariableRepresentationRef.model_validate(
        _put_contract(
            store,
            value,
            version="3.0",
            inputs=variable_representation_manifest_inputs(value),
        ).model_dump()
    )
    return ref, value


def _arithmetic(
    store: FileSystemCAS,
    *,
    ratio_id: str,
    denominator_id: str,
    target_id: str,
    year: int = 2024,
):
    """Run the existing Decimal owner; expected arithmetic stays a literal in tests."""
    authority_ref = store.put_bytes(
        b"fixture source authority", PutOptions(kind="fixture.authority", media_type="text/plain")
    )
    verifier_ref = store.put_bytes(
        b"fixture independent verifier",
        PutOptions(kind="fixture.verifier", media_type="text/plain"),
    )
    authority = AuthorityProjection(
        effective_score=Decimal("0.7"),
        authority_ref=authority_ref.artifact_id,
        verifier_provenance_ref=verifier_ref.artifact_id,
        authoritative_for="series_input",
    )
    sources = {
        "ratio": SourceSeries(
            variable_id=ratio_id,
            basis=BasisSignature(quantity_kind="flow", unit="ratio"),
            points=({"year": year, "value": Decimal("-0.03")},),
            authority=authority,
            observation_class="observed",
        ),
        "denominator": SourceSeries(
            variable_id=denominator_id,
            basis=BasisSignature(quantity_kind="flow", unit="usd"),
            points=({"year": year, "value": Decimal("200000000000")},),
            authority=authority,
            observation_class="observed",
        ),
    }
    source_refs = {
        role: _selected(store, persist_source_series(store, value))
        for role, value in sources.items()
    }
    family = TransformFamily.model_validate(
        {
            "family_id": "fixture.ratio_times_denominator",
            "method_id": "arithmetic.ratio_times_denominator",
            "method_version": "1.0",
            "input_specs": tuple(
                {"role": role, "basis": sources[role].basis} for role in ("denominator", "ratio")
            ),
            "output_basis": {"quantity_kind": "flow", "unit": "usd"},
            "year_domain_role": "ratio",
            "expression": {
                "operator": "multiply",
                "operands": (
                    {"operator": "current_value", "role": "ratio"},
                    {"operator": "current_value", "role": "denominator"},
                ),
            },
            "assumption_rules": ({"name": "fixture_context", "literal_value": "declared"},),
        }
    )
    registry = TransformFamilyRegistry(families=(family,))
    registry_ref = _selected(store, persist_transform_family_registry(store, registry))
    recipe = build_derivation_recipe(
        store,
        registry=registry,
        registry_ref=registry_ref,
        input_refs=source_refs,
        output_variable_id=target_id,
        family_id=family.family_id,
        method_version=family.method_version,
    )
    materialized = materialize_derivation(store, recipe)
    recipe_ref = _selected(store, persist_derivation_recipe_artifact(store, recipe))
    return SimpleNamespace(
        sources=sources,
        source_refs=source_refs,
        registry_ref=registry_ref,
        recipe=recipe,
        recipe_ref=recipe_ref,
        materialized=materialized,
    )


def _case(tmp_path: Path, *, declared_currency: str = "USD"):
    store = FileSystemCAS(tmp_path / "cas")
    target_ref, target = _definition(store, "government-fiscal-flow")
    ratio_ref, ratio_definition = _definition(store, "fiscal-flow-gdp-ratio")
    denominator_ref, denominator_definition = _definition(store, "gdp-flow")
    money = MoneyUnit(currency=declared_currency, nominal_year=2024, price_base="current")
    representations = {
        "target": _representation(
            store, target_ref, population="population:government", money=money
        ),
        "ratio": _representation(
            store,
            ratio_ref,
            population="population:government",
            money=money,
            numerator_ref=target_ref,
            denominator_ref=denominator_ref,
        ),
        "denominator": _representation(
            store, denominator_ref, population="population:economy", money=money
        ),
    }
    scope = ModelInputScope(
        population_ref="population:government",
        geography_ref="geography:fixture",
        jurisdiction_ref="jurisdiction:fixture",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        time_role="observation_time",
        period_basis="calendar_year",
    )
    binding_profile = MeasurementBindingProfile(
        schema_version="polisyos.catalog.measurement_binding_profile.v3",
        profile_id="fixture.annual_flow",
        revision="1",
        required_axes=(
            MeasurementAxis.QUANTITY_KIND,
            MeasurementAxis.MEASURE_FORM,
            MeasurementAxis.UNIT_ID,
            MeasurementAxis.TIME_SUPPORT,
            MeasurementAxis.MONEY_UNIT,
        ),
    )
    binding_profile_ref = MeasurementBindingProfileRef.model_validate(
        _put_contract(store, binding_profile, version="3.0").model_dump()
    )
    port = ModelInputPort(
        port_id="fixture-government-annual-flow",
        slot_id="fixture.annual_flow",
        state_path="fixture_flow",
        unit_id="usd",
        purpose="simulation_input",
        semantic_definition_ref=target_ref,
        representation_ref=representations["target"][0],
        binding_profile_ref=binding_profile_ref,
        scope=scope,
        physical_encoding=ModelInputPhysicalEncoding(
            shape=(), dtype="float32", max_absolute_error=Decimal("0")
        ),
    )
    artifact = _selected(
        store,
        store.put_json(
            {"typed": "fixture owner"},
            PutOptions(kind="fixture.owner", media_type="application/json"),
        ),
    )

    def ref(kind):
        return SelectedVariableBindingRef.model_validate(artifact.model_dump() | {"kind": kind})

    obligation = ModelInputObligation(
        context=ModelInputContext(
            run_id="fixture",
            candidate_id="fixture",
            candidate_content_hash=str(artifact.artifact_id),
            design_problem_ref="fixture",
        ),
        interface_ref=ref("runtime.quality.program_graph_input_interface"),
        program_graph_ref=ProgramGraphRef.model_validate(ref("foundry.program_graph").model_dump()),
        exec_plan_ref=ExecPlanRef.model_validate(ref("foundry.exec_plan").model_dump()),
        registry_bundle_ref=ref("core.registry_bundle"),
        input_bindings_ref=FoundryInputBindingsRef.model_validate(
            ref("foundry.input_bindings").model_dump()
        ),
        prestate_ref=StateSnapshotRef.model_validate(ref("foundry.state_snapshot").model_dump()),
        port=port,
        dependencies=(
            ProgramGraphInputDependency(
                node_id="fixture", kind="mechanism_read", first_required_step=0
            ),
        ),
    )
    obligation_ref = ref("runtime.quality.model_input_obligation")
    arithmetic = _arithmetic(
        store,
        ratio_id="fixture.fiscal-flow-gdp-ratio",
        denominator_id="fixture.gdp-flow",
        target_id="fixture.government-fiscal-flow",
    )
    loaded_roles = []
    for role, definition_ref, definition in (
        ("denominator", denominator_ref, denominator_definition),
        ("ratio", ratio_ref, ratio_definition),
    ):
        representation_ref, representation = representations[role]
        role_scope = scope.model_copy(update={"population_ref": representation.population_ref})
        source = ScopedSourceSelection(
            source_receipt_ref=ref("epoch.activated_overlay_admission_receipt"),
            source_passport_ref=ref("epoch.acquisition_passport_snapshot"),
            source_boundary_candidate_ref=ref("epoch.acquisition_semantic_boundary_candidate"),
            source_record_ref=ref("fixture.raw_source"),
            epoch_id=1,
            passport_id="fixture",
            dataset_id=f"fixture.{role}",
            dataset_version="1",
            source_watermark=str(artifact.artifact_id),
            observation_class="observed",
            raw_field=role,
            canonical_variable=f"{definition.namespace}.{definition.stable_id}",
            raw_unit=representation.unit_id,
            canonical_unit=representation.unit_id,
            unit_transform="identity",
            binding_id="field-binding:sha256:" + "a" * 64,
            aggregation_method="identity",
            is_proxy=False,
            declared_source_definition_ref=definition_ref,
            declared_source_representation_ref=representation_ref,
        )
        value = str(arithmetic.sources[role].points[0].value)
        occurrence = ScopedMeasurementOccurrence(
            source_scope=role_scope,
            source_receipt_ref=source.source_receipt_ref,
            source_passport_ref=source.source_passport_ref,
            source_boundary_candidate_ref=source.source_boundary_candidate_ref,
            source_record_ref=source.source_record_ref,
            observation_id=f"fixture.{role}",
            observation_content_sha256=str(artifact.artifact_id),
            dataset_id=source.dataset_id,
            dataset_version="1",
            source_watermark=str(artifact.artifact_id),
            raw_variable=role,
            canonical_variable=source.canonical_variable,
            country_code="fixture",
            year=2024,
            observation_class="observed",
            condition_json="{}",
            acquisition_method="registered_identity_identity_lift",
            raw_values=(value,),
            aggregation_method="identity",
            canonical_value=value,
            canonical_unit=representation.unit_id,
        )
        occurrence_ref = ScopedMeasurementOccurrenceRef.model_validate(
            _put_contract(store, occurrence).model_dump()
        )
        selection = DerivedMeasurementRole(
            role=role,
            source_series_ref=arithmetic.source_refs[role],
            occurrence_ref=occurrence_ref,
            definition_ref=definition_ref,
            representation_ref=representation_ref,
        )
        loaded_roles.append(
            ReplayedDerivedMeasurementRole(
                selection,
                occurrence,
                occurrence,
                source,
                definition,
                representation,
                arithmetic.sources[role],
            )
        )
    denominator, ratio = loaded_roles
    context = RatioDenominatorSourceContext(
        scope_note="Synthetic fiscal numerator and economy denominator; no empirical provider claim.",
        ratio_occurrence_ref=ratio.selection.occurrence_ref,
        ratio_definition_ref=ratio_ref,
        ratio_representation_ref=ratio.selection.representation_ref,
        denominator_occurrence_ref=denominator.selection.occurrence_ref,
        denominator_definition_ref=denominator_ref,
        denominator_representation_ref=denominator.selection.representation_ref,
        money_unit=money,
    )
    profile = DerivedInputProfile()
    basis = DerivedInputCorrespondenceBasis(
        profile_ref=persist_derived_input_profile(store, profile),
        source_context_ref=persist_ratio_denominator_source_context(store, context),
        model_input_obligation_ref=obligation_ref,
        model_interface_ref=SelectedVariableBindingRef.model_validate(
            obligation.interface_ref.model_dump()
        ),
        model_port_id=port.port_id,
        target_definition_ref=target_ref,
        target_representation_ref=port.representation_ref,
        binding_profile_ref=binding_profile_ref,
        scope=scope,
        year=2024,
        registry_ref=arithmetic.registry_ref,
        family_id=arithmetic.recipe.family.family_id,
        method_version=arithmetic.recipe.method_version,
        recipe_ref=arithmetic.recipe_ref,
        certificate_ref=_selected(store, arithmetic.materialized.certificate_artifact_ref),
        output_ref=_selected(store, arithmetic.materialized.derived_artifact_ref),
        roles=tuple(item.selection for item in loaded_roles),
    )
    arguments = {
        "basis": basis,
        "profile": profile,
        "source_context": context,
        "obligation_ref": obligation_ref,
        "obligation": obligation,
        "target_definition": target,
        "target_representation": representations["target"][1],
        "binding_profile": binding_profile,
        "units_registry": DEFAULT_UNITS_REGISTRY,
        "recipe": arithmetic.recipe,
        "series": arithmetic.materialized.series,
        "roles": tuple(loaded_roles),
    }
    return store, arguments


def test_fiscal_ratio_uses_exact_denominator_and_retains_candidate_limits(tmp_path: Path) -> None:
    store, arguments = _case(tmp_path)
    result = evaluate_derived_input_correspondence(**arguments)
    assert result.status == "candidate", result.refusal_codes
    assert result.value == Decimal("-6000000000")
    assert result.structural_correspondence == "recomputed"
    assert result.empirical_context == "institutionally_supplied"
    assert result.uncertainty_status == "not_established"
    assert "derivation_uncertainty_not_established" in result.limitation_codes
    basis = arguments["basis"]
    ref = persist_derived_input_correspondence(store, basis)
    assert load_derived_input_correspondence(FileSystemCAS(store.root), ref) == basis


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("numerator", "ratio_numerator_target_mismatch"),
        ("denominator", "ratio_denominator_definition_mismatch"),
        ("occurrence_forgery", "denominator_source_point_replay_mismatch"),
        ("source_point", "denominator_series_point_mismatch"),
        ("wrong_year", "denominator_series_point_mismatch"),
        ("price_base", "money_basis_mismatch"),
        ("unknown_base", "money_price_base_not_established"),
        ("release", "denominator_source_context_mismatch"),
        ("stock", "target_annual_absolute_flow_required"),
        ("fiscal_period", "exact_calendar_year_scope_required"),
        ("disjoint_geo", "role_geography_scope_mismatch"),
    ],
)
def test_derived_relation_refuses_near_semantics(
    tmp_path: Path, mutation: str, reason: str
) -> None:
    _, arguments = _case(tmp_path)
    assert evaluate_derived_input_correspondence(**arguments).status == "candidate"
    denominator, ratio = arguments["roles"]
    if mutation in {"numerator", "denominator"}:
        ratio = replace(
            ratio,
            representation=ratio.representation.model_copy(
                update={f"{mutation}_ref": ratio.selection.definition_ref}
            ),
        )
    elif mutation in {"source_point", "occurrence_forgery"}:
        occurrence = denominator.occurrence.model_copy(update={"canonical_value": "199999999999"})
        denominator = replace(
            denominator,
            occurrence=occurrence,
            replayed_occurrence=(
                occurrence if mutation == "source_point" else denominator.replayed_occurrence
            ),
        )
    elif mutation == "wrong_year":
        occurrence = denominator.occurrence.model_copy(
            update={
                "year": 2023,
                "source_scope": denominator.occurrence.source_scope.model_copy(
                    update={"period_start": date(2023, 1, 1), "period_end": date(2023, 12, 31)}
                ),
            }
        )
        denominator = replace(denominator, occurrence=occurrence, replayed_occurrence=occurrence)
    elif mutation == "price_base":
        denominator = replace(
            denominator,
            representation=denominator.representation.model_copy(
                update={
                    "money_unit": MoneyUnit(
                        currency="USD", nominal_year=2020, price_base="constant"
                    )
                }
            ),
        )
    elif mutation == "unknown_base":
        arguments["target_representation"] = arguments["target_representation"].model_copy(
            update={"money_unit": MoneyUnit(currency="USD", nominal_year=2024)}
        )
    elif mutation == "release":
        arguments["source_context"] = arguments["source_context"].model_copy(
            update={"denominator_occurrence_ref": ratio.selection.occurrence_ref}
        )
    elif mutation == "stock":
        arguments["target_representation"] = arguments["target_representation"].model_copy(
            update={"quantity_kind": "stock", "time_support": "state_start"}
        )
    elif mutation in {"fiscal_period", "disjoint_geo"}:
        field, value = (
            ("period_basis", "fiscal_year")
            if mutation == "fiscal_period"
            else ("geography_ref", "geography:elsewhere")
        )
        occurrence = denominator.occurrence.model_copy(
            update={
                "source_scope": denominator.occurrence.source_scope.model_copy(
                    update={field: value}
                )
            }
        )
        denominator = replace(denominator, occurrence=occurrence, replayed_occurrence=occurrence)
    arguments["roles"] = (denominator, ratio)
    refused = evaluate_derived_input_correspondence(**arguments)
    assert refused.status == "refused"
    assert reason in refused.refusal_codes


def test_singleton_projection_requires_one_value_without_broadcast(tmp_path: Path) -> None:
    _, arguments = _case(tmp_path)
    port = arguments["obligation"].port
    encoding = port.physical_encoding
    assert encoding is not None
    arguments["profile"] = DerivedInputProfile(output_projection="singleton_vector")
    arguments["obligation"] = arguments["obligation"].model_copy(
        update={
            "port": port.model_copy(
                update={"physical_encoding": encoding.model_copy(update={"shape": (1,)})}
            )
        }
    )
    assert evaluate_derived_input_correspondence(**arguments).status == "candidate"
    arguments["obligation"] = arguments["obligation"].model_copy(
        update={
            "port": port.model_copy(
                update={"physical_encoding": encoding.model_copy(update={"shape": (2,)})}
            )
        }
    )
    refused = evaluate_derived_input_correspondence(**arguments)
    assert refused.status == "refused"
    assert "declared_output_shape_required" in refused.refusal_codes


def test_consistent_currency_declarations_must_match_the_canonical_unit_owner(
    tmp_path: Path,
) -> None:
    _, valid = _case(tmp_path / "valid")
    assert evaluate_derived_input_correspondence(**valid).status == "candidate"
    _, wrong = _case(tmp_path / "wrong", declared_currency="UAH")
    # All four stored declarations agree with each other. The selected unit
    # owner's usd entry still denotes USD, independently of those declarations.
    assert wrong["target_representation"].money_unit == wrong["source_context"].money_unit
    assert all(
        role.representation.money_unit == wrong["source_context"].money_unit
        for role in wrong["roles"]
    )
    refused = evaluate_derived_input_correspondence(**wrong)
    assert refused.status == "refused"
    assert refused.refusal_codes == ("canonical_money_unit_mismatch",)
