"""Actual native source replay and certified derivation for method-input tests."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    load_model_input_obligation_set,
)
from polisyos.core.contracts.semantic_derived_binding import (
    DerivedInputProfile,
    DerivedMeasurementRole,
    RatioDenominatorSourceContext,
    persist_derived_input_profile,
    persist_ratio_denominator_source_context,
)
from polisyos.core.contracts.variable_binding import (
    ScopedMeasurementOccurrenceRef,
    replay_scoped_measurement_occurrence,
    scoped_measurement_occurrence_manifest_inputs,
    scoped_source_selection_from_passport_mapping,
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
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.runtime.quality.model_input_routing import (
    DerivedModelInputMaterialization,
    materialize_derived_model_input,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from tests._helpers.program_graph_tax_subsidy_input import ProgramGraphTaxSubsidyInputCase
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
from tests.unit.core.contracts.test_semantic_derived_binding import (
    _definition,
    _put_contract,
    _representation,
    _selected,
)
from tests.unit.runtime.quality.test_model_input_requirements import (
    _interface,
    _preflight,
)


def _replayed_occurrence(store, projection):
    (row,) = projection.observations
    passport = epoch_contract.load_verified_epoch_statement(
        store=store,
        ref=projection.passport_ref,
        expected_kind="epoch.acquisition_passport_snapshot",
    )
    boundary_ref = _selected(
        store, ArtifactRef.model_validate(passport["semantic_boundary_candidate_ref"])
    )
    boundary = epoch_contract.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
        epoch_contract.load_verified_epoch_statement(
            store=store,
            ref=boundary_ref,
            expected_kind="epoch.acquisition_semantic_boundary_candidate",
        )
    )
    source = scoped_source_selection_from_passport_mapping(
        passport,
        source_receipt_ref=_selected(store, projection.receipt_ref),
        source_passport_ref=_selected(store, projection.passport_ref),
        source_boundary_candidate_ref=boundary_ref,
        source_record_ref=_selected(store, boundary.source_record_ref),
    )
    occurrence = replay_scoped_measurement_occurrence(
        catalog_read_api.read_scoped_measurement_source_body(
            store, passport_mapping=passport, source_selection=source
        ),
        observation_id=row.observation.observation_id,
        source_selection=source,
        unit_transform_evidence=None,
    )
    ref = ScopedMeasurementOccurrenceRef.model_validate(
        _put_contract(
            store, occurrence, inputs=scoped_measurement_occurrence_manifest_inputs(occurrence)
        ).model_dump(mode="python")
    )
    return occurrence, ref


def materialize_selected_method_input_case(
    case: ProgramGraphTaxSubsidyInputCase,
    metadata: dict[str, Any],
    *,
    ratio_value: Decimal = Decimal("-0.03"),
    denominator_value: Decimal = Decimal("200000000000"),
) -> DerivedModelInputMaterialization:
    """Materialize a fixture-scoped annual ratio times GDP through real owners.

    The caller supplies synthetic transport data, not a bound canonical value.
    Native admission and independent occurrence replay produce the exact source
    points consumed by the existing Core Decimal engine and Foundry binding gate.
    The external empirical context remains explicitly unestablished.
    """
    store = case.store
    candidate = validate_core_model_json_artifact(
        PolicyCandidateSchema, store, case.policy_candidate_ref
    )
    context = ModelInputContext(
        run_id="selected-method-input-test",
        candidate_id=candidate.candidate_id,
        candidate_content_hash=str(case.policy_candidate_ref.artifact_id),
        design_problem_ref=str(case.trinity_ref.artifact_id),
        candidate_source_ref=case.policy_candidate_ref,
    )
    preflight = _preflight(case, _interface(case), context, steps=(0,))
    selected_set, (obligation,) = load_model_input_obligation_set(
        store, preflight.obligation_set_ref
    )
    (obligation_ref,) = selected_set.obligation_refs
    ratio_ref, _ = _definition(store, "aggregate-period-flow-gdp-ratio")
    denominator_ref, _ = _definition(store, "economy-gdp-flow")
    representations = {
        "ratio": _representation(
            store,
            ratio_ref,
            population="population:government",
            money=metadata["money"],
            numerator_ref=metadata["target_ref"],
            denominator_ref=denominator_ref,
        ),
        "denominator": _representation(
            store, denominator_ref, population="population:economy", money=metadata["money"]
        ),
    }
    variable_ids = {
        "ratio": "fixture.aggregate-period-flow-gdp-ratio",
        "denominator": "fixture.economy-gdp-flow",
    }
    definitions = {"ratio": ratio_ref, "denominator": denominator_ref}
    specs = tuple(
        {
            "target_variable": variable_ids[role],
            "raw_field": role,
            "raw_unit": unit,
            "canonical_unit": unit,
            "unit_transform_ref": f"fabric://units/{unit}-identity/v1",
            "valid_min": minimum,
            "valid_max": maximum,
            "source_measure_scope": {
                "population": population,
                "temporal_granularity": "annual",
                "jurisdiction_ref": "jurisdiction:fixture",
                "time_period_basis": "calendar_year",
                "source_geography_id": "UA",
                "geography_ref": "UA",
            },
            "source_semantic_definition_ref": definitions[role],
            "source_representation_ref": representations[role][0],
        }
        for role, population, unit, minimum, maximum in (
            ("ratio", "population:government", "ratio", -1, 1),
            ("denominator", "population:economy", "usd", 0, 300_000_000_000),
        )
    )
    fixture_id = hashlib.sha256(f"{ratio_value}:{denominator_value}".encode()).hexdigest()[:16]
    owner = make_native_multivariable_active_projections(
        case.store_root.parent / f"sources-{fixture_id}",
        source_rows=[
            {
                "country_code": "UA",
                "year": 2024,
                "ratio": float(ratio_value),
                "denominator": float(denominator_value),
                "condition_json": {},
            }
        ],
        variable_specs=specs,
        artifact_store=store,
        return_selected_raw_profile=True,
    )
    try:
        replayed = {
            role: _replayed_occurrence(store, owner.projections[variable_id])
            for role, variable_id in variable_ids.items()
        }
        sources = {
            role: SourceSeries(
                variable_id=variable_ids[role],
                basis=BasisSignature(
                    quantity_kind="flow", unit="ratio" if role == "ratio" else "usd"
                ),
                points=({"year": 2024, "value": Decimal(occurrence.canonical_value)},),
                authority=AuthorityProjection(
                    effective_score=Decimal("0.7"),
                    authority_ref=occurrence.source_receipt_ref.artifact_id,
                    verifier_provenance_ref=occurrence.source_passport_ref.artifact_id,
                    authoritative_for="series_input",
                ),
                observation_class="observed",
            )
            for role, (occurrence, _) in replayed.items()
        }
        source_refs = {
            role: _selected(store, persist_source_series(store, source))
            for role, source in sources.items()
        }
        family = TransformFamily.model_validate(
            {
                "family_id": "fixture.ratio_times_denominator",
                "method_id": "arithmetic.ratio_times_denominator",
                "method_version": "1.0",
                "input_specs": tuple(
                    {"role": role, "basis": sources[role].basis}
                    for role in ("denominator", "ratio")
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
            output_variable_id="fixture.aggregate-period-flow",
            family_id=family.family_id,
            method_version=family.method_version,
        )
        recipe_ref = _selected(store, persist_derivation_recipe_artifact(store, recipe))
        produced = materialize_derivation(store, recipe)
        roles = tuple(
            DerivedMeasurementRole(
                role=role,
                source_series_ref=source_refs[role],
                occurrence_ref=replayed[role][1],
                definition_ref=definitions[role],
                representation_ref=representations[role][0],
            )
            for role in ("denominator", "ratio")
        )
        by_role = {role.role: role for role in roles}
        source_context_ref = persist_ratio_denominator_source_context(
            store,
            RatioDenominatorSourceContext(
                scope_note="Fixture-owned annual government period-flow/GDP context; no external empirical claim.",
                ratio_occurrence_ref=by_role["ratio"].occurrence_ref,
                ratio_definition_ref=ratio_ref,
                ratio_representation_ref=representations["ratio"][0],
                denominator_occurrence_ref=by_role["denominator"].occurrence_ref,
                denominator_definition_ref=denominator_ref,
                denominator_representation_ref=representations["denominator"][0],
                money_unit=metadata["money"],
            ),
        )
        profile_ref = persist_derived_input_profile(store, DerivedInputProfile())
        materialized = materialize_derived_model_input(
            store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=preflight.obligation_set_ref,
            model_input_obligation_ref=obligation_ref,
            profile_ref=profile_ref,
            source_context_ref=source_context_ref,
            recipe_ref=recipe_ref,
            certificate_ref=produced.certificate_artifact_ref,
            output_ref=produced.derived_artifact_ref,
            roles=roles,
            year=2024,
            binding_id="selected-period-flow",
        )
        metadata.update(
            preflight=preflight,
            obligation=obligation,
            obligation_ref=obligation_ref,
            recipe_ref=recipe_ref,
            certificate_ref=produced.certificate_artifact_ref,
            output_ref=produced.derived_artifact_ref,
            roles=roles,
            derived_profile_ref=profile_ref,
            source_context_ref=source_context_ref,
        )
        return materialized
    finally:
        owner.overlay.close()
