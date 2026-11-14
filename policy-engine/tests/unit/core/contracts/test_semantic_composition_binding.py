"""Pure projection predicates; native admission is exercised by Foundry tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.core.contracts.semantic_composition_binding import (
    RegisteredDerivationRoleBasis,
    RegisteredDerivedInputContext,
    RegisteredDerivedInputProfile,
    RegisteredMeasurementRole,
    RegisteredRoleScope,
    RegisteredSemanticBasis,
    load_registered_derived_input_profile,
    persist_registered_derived_input_context,
    persist_registered_derived_input_profile,
    recompute_native_derivation_source_projection,
    verify_registered_derived_family,
)
from polisyos.core.contracts.variable_binding import SelectedVariableBindingRef
from polisyos.core.derivations import (
    TransformFamily,
    TransformFamilyRegistry,
    persist_transform_family_registry,
)
from tests.unit.core.contracts.test_semantic_derived_binding import _case


def _projection_inputs(tmp_path):
    store, old = _case(tmp_path)
    names = {"denominator": "base", "ratio": "share"}
    roles = {names[item.selection.role]: item for item in old["roles"]}
    family = TransformFamily.model_validate(
        {
            "family_id": "registered.family",
            "method_id": "arithmetic.registered_product",
            "method_version": "1.0",
            "input_specs": tuple(
                {
                    "role": role,
                    "basis": item.series.basis,
                    "allowed_input_kinds": ("candidate_source",),
                }
                for role, item in roles.items()
            ),
            "output_basis": {"quantity_kind": "flow", "unit": "usd"},
            "year_domain_role": "base",
            "expression": {
                "operator": "multiply",
                "operands": (
                    {"operator": "current_value", "role": "share"},
                    {"operator": "current_value", "role": "base"},
                ),
            },
            "assumption_rules": ({"name": "empirical_context", "literal_value": "unknown"},),
        }
    )
    registry_ref = persist_transform_family_registry(
        store, TransformFamilyRegistry(families=(family,))
    )
    profile = RegisteredDerivedInputProfile(
        registry_ref=SelectedVariableBindingRef.model_validate(
            registry_ref.model_dump(mode="python")
        ),
        family_id=family.family_id,
        method_version=family.method_version,
        ratio_role="share",
        denominator_role="base",
        inputs=tuple(
            RegisteredDerivationRoleBasis(
                role=role,
                basis=RegisteredSemanticBasis(
                    semantic_definition_ref=item.selection.definition_ref,
                    representation_ref=item.selection.representation_ref,
                    binding_profile_ref=old["obligation"].port.binding_profile_ref,
                ),
            )
            for role, item in roles.items()
        ),
        output=RegisteredSemanticBasis(
            semantic_definition_ref=old["obligation"].port.semantic_definition_ref,
            representation_ref=old["obligation"].port.representation_ref,
            binding_profile_ref=old["obligation"].port.binding_profile_ref,
        ),
    )
    profile_ref = persist_registered_derived_input_profile(store, profile)
    context = RegisteredDerivedInputContext(
        profile_ref=profile_ref,
        obligation_set_ref=old["obligation_ref"].model_copy(
            update={"kind": "runtime.quality.model_input_obligation_set"}
        ),
        model_input_obligation_ref=old["obligation_ref"],
        model_interface_ref=old["basis"].model_interface_ref,
        model_port_id=old["obligation"].port.port_id,
        registry_bundle_ref=SelectedVariableBindingRef.model_validate(
            old["obligation"].registry_bundle_ref.model_dump(mode="python")
        ),
        year=2024,
        output_scope=old["obligation"].port.scope,
        roles=tuple(
            RegisteredMeasurementRole(role=role, occurrence_ref=item.selection.occurrence_ref)
            for role, item in roles.items()
        ),
        role_scopes=tuple(
            RegisteredRoleScope(role=role, scope=item.occurrence.source_scope)
            for role, item in roles.items()
        ),
    )
    context_ref = persist_registered_derived_input_context(store, context)
    source = roles["base"]
    # Exact selected semantic refs may legitimately have a different canonical
    # source label. Labels identify source records, not the variable's meaning.
    occurrence = source.occurrence.model_copy(
        update={"canonical_variable": "provider.legacy_total"}
    )
    selection = source.source_selection.model_copy(
        update={"canonical_variable": "provider.legacy_total"}
    )
    return (
        store,
        family,
        {
            "profile_ref": profile_ref,
            "profile": profile,
            "context_ref": context_ref,
            "context": context,
            "role": "base",
            "occurrence_ref": source.selection.occurrence_ref,
            "occurrence": occurrence,
            "replayed_occurrence": occurrence,
            "source_selection": selection,
            "definition": source.definition,
            "representation": source.representation,
            "binding_profile": old["binding_profile"],
        },
    )


def test_registered_source_projection_uses_refs_and_keeps_unknown_authority(tmp_path):
    store, family, args = _projection_inputs(tmp_path)
    verify_registered_derived_family(args["profile"], family)
    result = recompute_native_derivation_source_projection(**args)
    assert result.canonical_value == Decimal("200000000000")
    assert result.source_variable_id == "provider.legacy_total"
    assert result.source_value_correspondence == result.source_basis_correspondence == "recomputed"
    assert result.empirical_authority == "not_established"
    assert "effective_score" not in result.model_dump(mode="json")
    assert load_registered_derived_input_profile(store, args["profile_ref"]) == args["profile"]


@pytest.mark.parametrize(
    "mutation", ["point", "definition_ref", "year", "price_base", "source_label"]
)
def test_registered_source_projection_refuses_distinguishing_variants(tmp_path, mutation):
    _, _, args = _projection_inputs(tmp_path)
    if mutation == "point":
        args["occurrence"] = args["occurrence"].model_copy(update={"canonical_value": "0"})
    elif mutation == "definition_ref":
        args["source_selection"] = args["source_selection"].model_copy(
            update={
                "declared_source_definition_ref": args["profile"].output.semantic_definition_ref,
            }
        )
    elif mutation == "year":
        args["occurrence"] = args["occurrence"].model_copy(update={"year": 2023})
        args["replayed_occurrence"] = args["occurrence"]
    elif mutation == "price_base":
        args["representation"] = args["representation"].model_copy(
            update={
                "money_unit": args["representation"].money_unit.model_copy(
                    update={"price_base": None}
                ),
            }
        )
    else:
        args["source_selection"] = args["source_selection"].model_copy(
            update={"canonical_variable": "foreign.actual_source"}
        )
    with pytest.raises(ValueError, match=r"^composition_input_native_"):
        recompute_native_derivation_source_projection(**args)
