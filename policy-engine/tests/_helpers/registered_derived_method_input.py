"""Real native rows and unscored v3 composition for selected method tests."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

from polisyos.core.artifacts import (
    ArtifactRef,
    artifact_ref_identity_key,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    load_model_input_obligation_set,
)
from polisyos.core.contracts.semantic_composition_binding import (
    RegisteredDerivationRoleBasis,
    RegisteredDerivedInputProfile,
    RegisteredDerivedModelInputRequest,
    RegisteredMeasurementRole,
    RegisteredSemanticBasis,
    persist_registered_derived_input_profile,
)
from polisyos.core.contracts.semantic_input_binding import load_resolved_input_binding_manifest
from polisyos.core.contracts.variable_binding import SelectedVariableBindingRef
from polisyos.core.derivations import (
    TransformFamily,
    TransformFamilyRegistry,
    persist_transform_family_registry,
)
from polisyos.data_forge.read_api import catalog
from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
from polisyos.runtime.quality.model_input_requirements import ProgramGraphInputPreflight
from polisyos.runtime.quality.model_input_routing import (
    DerivedModelInputMaterialization,
    materialize_registered_derived_model_inputs,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from tests._helpers.program_graph_tax_subsidy_input import ProgramGraphTaxSubsidyInputCase
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
from tests.unit.core.contracts.test_semantic_derived_binding import _definition, _representation
from tests.unit.runtime.quality.test_model_input_requirements import _interface, _preflight


def prepare_registered_method_input_preflight(
    case: ProgramGraphTaxSubsidyInputCase,
) -> ProgramGraphInputPreflight:
    """Derive the real complete input denominator of this persisted candidate."""
    candidate = validate_core_model_json_artifact(
        PolicyCandidateSchema, case.store, case.policy_candidate_ref
    )
    context = ModelInputContext(
        run_id="registered-native-method-input-test",
        candidate_id=candidate.candidate_id,
        candidate_content_hash=str(case.policy_candidate_ref.artifact_id),
        design_problem_ref=str(case.trinity_ref.artifact_id),
        candidate_source_ref=case.policy_candidate_ref,
    )
    return _preflight(case, _interface(case), context, steps=(0,))


def materialize_registered_method_input_case(
    case: ProgramGraphTaxSubsidyInputCase,
    metadata: dict[str, Any],
    *,
    ratio_value: Decimal = Decimal("-0.03"),
    denominator_value: Decimal = Decimal("200000000000"),
    binding_id: str = "registered-period-flow",
) -> DerivedModelInputMaterialization:
    """Replay real native rows through the registered v3 materializer.

    The mathematical family uses explicit nondefault role names, and source
    variable labels deliberately differ from semantic-definition stable IDs.
    All data and registration declarations are controlled synthetic inputs;
    unknown empirical authority stays unscored throughout the complete chain.
    """
    preflight = prepare_registered_method_input_preflight(case)
    selected_set, _ = load_model_input_obligation_set(case.store, preflight.obligation_set_ref)
    (obligation_ref,) = selected_set.obligation_refs
    request = prepare_registered_method_input_request(
        case,
        metadata,
        preflight=preflight,
        model_input_obligation_ref=obligation_ref,
        ratio_value=ratio_value,
        denominator_value=denominator_value,
        binding_id=binding_id,
    )
    batch = materialize_registered_derived_model_inputs(
        case.store,
        base_data_snapshot_ref=case.data_snapshot_ref,
        obligation_set_ref=preflight.obligation_set_ref,
        inputs=(request,),
    )
    materialized = DerivedModelInputMaterialization(
        data_snapshot_ref=batch.data_snapshot_ref,
        resolved_binding_manifest_ref=batch.resolved_binding_manifest_ref,
        correspondence_ref=batch.correspondence_refs[0],
        input_bindings_ref=batch.input_bindings_ref,
    )
    (selected,) = load_resolved_input_binding_manifest(
        case.store, materialized.resolved_binding_manifest_ref
    ).derivations
    metadata.update(
        batch_materialization=batch,
        recipe_ref=selected.recipe_ref,
        certificate_ref=selected.certificate_ref,
        output_ref=selected.output_ref,
    )
    return materialized


def prepare_registered_method_input_request(
    case: ProgramGraphTaxSubsidyInputCase,
    metadata: dict[str, Any],
    *,
    preflight: ProgramGraphInputPreflight,
    model_input_obligation_ref: ArtifactRef,
    ratio_value: Decimal = Decimal("-0.03"),
    denominator_value: Decimal = Decimal("200000000000"),
    binding_id: str = "registered-period-flow",
) -> RegisteredDerivedModelInputRequest:
    """Prepare real selected native role inputs for one exact obligation member.

    This emits no binding manifest. The plural Runtime producer owns the full
    required-port denominator and materializes all requests atomically.
    """
    store = case.store
    selected_set, obligations = load_model_input_obligation_set(store, preflight.obligation_set_ref)
    members = {
        artifact_ref_identity_key(ref): member
        for ref, member in zip(selected_set.obligation_refs, obligations, strict=True)
    }
    obligation = members.get(artifact_ref_identity_key(model_input_obligation_ref))
    if obligation is None or obligation.port != metadata["port"]:
        raise ValueError("registered_method_fixture_obligation_member_required")
    obligation_ref = model_input_obligation_ref
    ratio_role, denominator_role = "rate_input", "scale_input"
    ratio_definition, _ = _definition(store, "registered-source-ratio")
    denominator_definition, _ = _definition(store, "registered-source-total")
    source_definitions = {
        ratio_role: ratio_definition,
        denominator_role: denominator_definition,
    }
    source_representations = {
        ratio_role: _representation(
            store,
            ratio_definition,
            population=obligation.port.scope.population_ref,
            money=metadata["money"],
            numerator_ref=obligation.port.semantic_definition_ref,
            denominator_ref=denominator_definition,
        )[0],
        denominator_role: _representation(
            store, denominator_definition, population="population:economy", money=metadata["money"]
        )[0],
    }
    aliases = {ratio_role: "provider.share_series", denominator_role: "provider.total_series"}
    units = {ratio_role: "ratio", denominator_role: "usd"}
    profile_for_source = obligation.port.binding_profile_ref
    family = TransformFamily.model_validate(
        {
            "family_id": "registered.flow_from_share",
            "method_id": "arithmetic.registered_multiply",
            "method_version": "1.0",
            "input_specs": tuple(
                {
                    "role": role,
                    "basis": {"quantity_kind": "flow", "unit": units[role]},
                    "allowed_input_kinds": ("candidate_source",),
                }
                for role in (ratio_role, denominator_role)
            ),
            "output_basis": {"quantity_kind": "flow", "unit": "usd"},
            # With exact common requested years, either registered role can
            # own the arithmetic year domain; no literal role-name proxy.
            "year_domain_role": denominator_role,
            "expression": {
                "operator": "multiply",
                "operands": (
                    {"operator": "current_value", "role": denominator_role},
                    {"operator": "current_value", "role": ratio_role},
                ),
            },
            "assumption_rules": ({"name": "empirical_coupling", "literal_value": "unknown"},),
        }
    )
    registry_ref = persist_transform_family_registry(
        store,
        TransformFamilyRegistry(families=(family,)),
        registry_bundle_ref=case.registry_bundle_ref,
    )
    profile = RegisteredDerivedInputProfile(
        registry_ref=SelectedVariableBindingRef.model_validate(
            registry_ref.model_dump(mode="python")
        ),
        family_id=family.family_id,
        method_version=family.method_version,
        ratio_role=ratio_role,
        denominator_role=denominator_role,
        inputs=tuple(
            RegisteredDerivationRoleBasis(
                role=role,
                basis=RegisteredSemanticBasis(
                    semantic_definition_ref=source_definitions[role],
                    representation_ref=source_representations[role],
                    binding_profile_ref=profile_for_source,
                ),
            )
            for role in (ratio_role, denominator_role)
        ),
        output=RegisteredSemanticBasis(
            semantic_definition_ref=obligation.port.semantic_definition_ref,
            representation_ref=obligation.port.representation_ref,
            binding_profile_ref=obligation.port.binding_profile_ref,
        ),
    )
    profile_ref = persist_registered_derived_input_profile(store, profile)
    specs = tuple(
        {
            "target_variable": aliases[role],
            "raw_field": role,
            "raw_unit": units[role],
            "canonical_unit": units[role],
            "unit_transform_ref": f"fabric://units/{units[role]}-identity/v1",
            "valid_min": -1 if role == ratio_role else 0,
            "valid_max": 1 if role == ratio_role else 300_000_000_000,
            "source_measure_scope": {
                "population": obligation.port.scope.population_ref
                if role == ratio_role
                else "population:economy",
                "temporal_granularity": "annual",
                "jurisdiction_ref": obligation.port.scope.jurisdiction_ref,
                "time_period_basis": "calendar_year",
                "source_geography_id": "UA",
                "geography_ref": obligation.port.scope.geography_ref,
            },
            "source_semantic_definition_ref": source_definitions[role],
            "source_representation_ref": source_representations[role],
        }
        for role in (ratio_role, denominator_role)
    )
    fixture_id = hashlib.sha256(
        f"{binding_id}:{ratio_value}:{denominator_value}".encode()
    ).hexdigest()[:16]
    owner = make_native_multivariable_active_projections(
        case.store_root.parent / f"registered-sources-{fixture_id}",
        source_rows=[
            {
                "country_code": "UA",
                "year": 2024,
                ratio_role: float(ratio_value),
                denominator_role: float(denominator_value),
                "condition_json": {},
            }
        ],
        variable_specs=specs,
        artifact_store=store,
        return_selected_raw_profile=True,
    )
    try:
        roles = []
        native_sources = {}
        for role in (ratio_role, denominator_role):
            projection = owner.projections[aliases[role]]
            (row,) = projection.observations
            passport = AdmissionPassport.model_validate(
                epoch_contract.load_verified_epoch_statement(
                    store=store,
                    ref=projection.passport_ref,
                    expected_kind="epoch.acquisition_passport_snapshot",
                )
            )
            occurrence_ref = catalog.materialize_activated_measurement_occurrence(
                store,
                owner.overlay,
                receipt_ref=projection.receipt_ref,
                passport=passport,
                authority=owner.authority,
                observation_id=row.observation.observation_id,
            )
            roles.append(RegisteredMeasurementRole(role=role, occurrence_ref=occurrence_ref))
            native_sources[role] = {
                "occurrence_ref": occurrence_ref,
                "source_receipt_ref": projection.receipt_ref,
                "source_passport_ref": projection.passport_ref,
                "observation_id": row.observation.observation_id,
                "passport": passport,
                "source_basis": profile.inputs[len(roles) - 1].basis,
            }
        metadata.update(
            registered_profile=profile,
            registered_profile_ref=profile_ref,
            role_occurrences=tuple(roles),
            native_sources=native_sources,
            preflight=preflight,
            obligation=obligation,
            obligation_ref=obligation_ref,
            binding_id=binding_id,
        )
        return RegisteredDerivedModelInputRequest(
            model_input_obligation_ref=SelectedVariableBindingRef.model_validate(
                obligation_ref.model_dump(mode="python")
            ),
            profile_ref=profile_ref,
            role_occurrences=tuple(roles),
            binding_id=binding_id,
        )
    finally:
        owner.overlay.close()
