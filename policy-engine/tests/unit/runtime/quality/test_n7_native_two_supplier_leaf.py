"""Exercise two declared alternatives for one N7 model-input source leaf.

The Catalog declarations, compiler target, and persisted N7 bundle are real
fixture artifacts. The Generic invocation is component-marked; this test does
not establish an admitted action, independent suppliers, or numerical execution.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.semantic_composition_binding import (
    RegisteredDerivedInputProfile,
    persist_registered_derived_input_profile,
)
from polisyos.core.contracts.variable_binding import load_variable_representation
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.runtime.quality.acquisition_planner import (
    load_n7_derivation_bundle,
    n7_pending_unique_derivation_source_gaps,
)
from polisyos.runtime.quality.acquisition_route_loop import NativeDerivationLeafProviderSelection
from polisyos.runtime.quality.acquisition_world_growth import NativeDerivationPlanningRoleSupplier
from polisyos.runtime.quality.n7_native_derivation_resolver import (
    validate_registered_derivation_role_input_gap,
)
from tests._helpers.lane01_wdi_profiles import (
    GDP_PROFILE,
    UNEMPLOYMENT_PROFILE,
    FixtureWDIRegisteredSourceSemantics,
    FixtureWDIRoleBinding,
    build_fixture_wdi_authority_bundle,
)
from tests.unit.runtime.quality import test_n7_native_derivation_resolver as fixture_owner
from tests.unit.runtime.quality import test_n7_registered_derivation_plan as registered_fixture


@pytest.fixture
def selected_case(tmp_path: Path):
    """Reuse the model/compiler owner fixture with an explicitly component-only join."""
    case = fixture_owner.prepare_selected_plan_case(
        tmp_path / "case", role_populations=fixture_owner._ROLE_POPULATIONS
    )
    try:
        # The selected denominator is an explicit test-owned GDP definition.
        # It remains candidate data, not evidence of empirical GDP.
        store = case["case"].store
        old_roles = {row.role: row for row in case["profile"].inputs}
        old_ratio = old_roles["ratio"]
        ratio_representation = load_variable_representation(
            store, old_ratio.basis.representation_ref
        )
        money = ratio_representation.money_unit
        assert money is not None
        gdp_definition_ref, _ = registered_fixture._definition(store, "gdp-flow")
        gdp_representation_ref, _ = registered_fixture._representation(
            store,
            gdp_definition_ref,
            population=fixture_owner._ROLE_POPULATIONS["denominator"],
            money=money,
        )
        ratio_representation_ref, _ = registered_fixture._representation(
            store,
            old_ratio.basis.semantic_definition_ref,
            population=fixture_owner._ROLE_POPULATIONS["ratio"],
            money=money,
            numerator_ref=case["target"].port.semantic_definition_ref,
            denominator_ref=gdp_definition_ref,
        )
        replacement_inputs = []
        for row in case["profile"].inputs:
            basis = row.basis.model_copy(
                update=(
                    {
                        "semantic_definition_ref": gdp_definition_ref,
                        "representation_ref": gdp_representation_ref,
                    }
                    if row.role == "denominator"
                    else {"representation_ref": ratio_representation_ref}
                )
            )
            replacement_inputs.append(row.model_copy(update={"basis": basis}))
        case["profile"] = RegisteredDerivedInputProfile.model_validate(
            case["profile"]
            .model_copy(update={"inputs": tuple(replacement_inputs)})
            .model_dump(mode="python")
        )
        case["profile_ref"] = persist_registered_derived_input_profile(store, case["profile"])
        yield case
    finally:
        case["case"].close()


def _source_snapshot(case: dict[str, Any], path: Path, *, role: str, suffix: str):
    """Persist a real Catalog declaration for an explicit model-role scope."""
    store = case["case"].store
    row = next(item for item in case["profile"].inputs if item.role == role)
    representation = load_variable_representation(store, row.basis.representation_ref)
    requested = case["target"].port.scope
    assert representation.population_ref is not None
    scope = {
        "population": representation.population_ref,
        "temporal_granularity": representation.temporal_granularity,
        "jurisdiction_ref": requested.jurisdiction_ref,
        "time_period_basis": requested.period_basis,
        "source_geography_id": "UKR",
        "geography_ref": requested.geography_ref,
    }
    if role == "ratio":
        assert representation.denominator_ref is not None
        scope.update(
            denominator=str(representation.denominator_ref.artifact_id),
            quantity_kind="share_of_denominator",
        )
        profile = replace(
            UNEMPLOYMENT_PROFILE,
            construct="fixture.balance_share_of_gdp",
            indicator_id="GC.BAL.CASH.GD.ZS",
            source_title="Controlled fiscal balance (% of GDP)",
            source_description="Synthetic annual fiscal balance as a share of GDP.",
            target_slot="fixture.balance_share_of_gdp",
            source_provenance_class="observed",
            population=representation.population_ref,
            denominator=str(representation.denominator_ref.artifact_id),
            quantity_kind="share_of_denominator",
            valid_min=None,
            valid_max=None,
            country_code="UKR",
            country_id="UA",
        )
    else:
        profile = replace(
            GDP_PROFILE,
            source_description=f"Synthetic annual current-USD GDP declaration {suffix}.",
            population=representation.population_ref,
            country_code="UKR",
            country_id="UA",
        )
    semantics = FixtureWDIRegisteredSourceSemantics(
        source_semantic_definition_ref=row.basis.semantic_definition_ref,
        source_representation_ref=row.basis.representation_ref,
        source_measure_scope=scope,
        country_codes=("UKR",),
    )
    authority, (entry,) = build_fixture_wdi_authority_bundle(
        path,
        (profile,),
        role_bindings={
            profile.target_slot: FixtureWDIRoleBinding(
                attempt_ids=(f"n7-two-supplier-{suffix}",),
                registered_source_semantics=semantics,
            )
        },
    )
    ref = catalog_read_api.persist_acquisition_supplier_declaration(
        store, authority, entry_id=entry.entry_id
    )
    declaration = catalog_read_api.load_acquisition_supplier_declaration(store, ref)
    provider = NativeDerivationLeafProviderSelection(
        source_node_id=f"component-source-{role}",
        supplier_ref=ref,
        authority_entry_id=entry.entry_id,
        connector_id=declaration.connector_id,
    )
    return {
        "role": role,
        "entry": entry,
        "ref": ref,
        "declaration": declaration,
        "selection_row": NativeDerivationPlanningRoleSupplier(
            role=role, provider=provider, source_declaration_ref=ref
        ),
    }


def _validate_supplier(case: dict[str, Any], gap: Any, snapshot: dict[str, Any]) -> str:
    return validate_registered_derivation_role_input_gap(
        case["case"].store,
        gap,
        supplier_ref=snapshot["ref"],
        authority_entry_id=snapshot["entry"].entry_id,
        connector_id=snapshot["declaration"].connector_id,
        expected_registered_profile_ref=case["profile_ref"],
        expected_obligation_set_ref=case["obligation_set_ref"],
        expected_target_obligation_ref=case["target_ref"],
        expected_routing_report_ref=case["routing_ref"],
    )


def test_n7_two_declared_suppliers_share_one_leaf_and_replan_after_removal(
    selected_case: dict[str, Any], tmp_path: Path, record_property: Any
) -> None:
    """Reopen the two choices, fail on missing inputs, and replan one survivor."""
    case = selected_case
    store = case["case"].store
    ratio = _source_snapshot(case, tmp_path / "ratio", role="ratio", suffix="ratio")
    first = _source_snapshot(case, tmp_path / "first", role="denominator", suffix="first")
    second = _source_snapshot(case, tmp_path / "second", role="denominator", suffix="second")
    ratio_role = next(item for item in case["profile"].inputs if item.role == "ratio")
    gdp_role = next(item for item in case["profile"].inputs if item.role == "denominator")
    ratio_representation = load_variable_representation(store, ratio_role.basis.representation_ref)
    assert ratio_representation.denominator_ref == gdp_role.basis.semantic_definition_ref
    assert ratio["entry"].raw_unit == "percent"
    assert ratio["entry"].canonical_unit == "ratio"
    assert ratio["entry"].source_measure_scope.denominator == str(
        gdp_role.basis.semantic_definition_ref.artifact_id
    )
    assert (
        first["entry"].catalog_raw_variable
        == second["entry"].catalog_raw_variable
        == ("NY.GDP.MKTP.CD")
    )
    alternatives = (first, second)
    alternative_keys = {artifact_ref_identity_key(row["ref"]) for row in alternatives}
    assert len(alternative_keys) == 2
    assert first["entry"].entry_id != second["entry"].entry_id
    assert first["entry"].target_variable == second["entry"].target_variable
    assert first["entry"].source_semantic_definition_ref == (
        second["entry"].source_semantic_definition_ref
    )
    assert first["entry"].source_representation_ref == (second["entry"].source_representation_ref)

    selection = fixture_owner._selection(case, (ratio, first, second))
    selected_ref = fixture_owner._resolve(case, selection)
    assert type(selected_ref) is ArtifactRef
    bundle, leaf, gap = fixture_owner._role_gap(case, selected_ref, "denominator")
    for name, ref in (
        ("gdp_source_a", first["ref"]),
        ("gdp_source_b", second["ref"]),
        ("ratio_source", ratio["ref"]),
        ("gdp_definition", gdp_role.basis.semantic_definition_ref),
        ("gdp_representation", gdp_role.basis.representation_ref),
        ("ratio_representation", ratio_role.basis.representation_ref),
        ("registered_profile", case["profile_ref"]),
        ("selected_bundle", selected_ref),
    ):
        record_property(name, json.dumps(ref.model_dump(mode="json"), sort_keys=True))
    record_property("test_cas_root", str(store.root))
    assert bundle.authority_purpose == "candidate_acquisition_routing_only"
    assert bundle.input_closure_status == "partial"
    assert bundle.target_satisfaction_status == "unsatisfied"
    assert leaf.selected_supplier_ref is None
    assert {artifact_ref_identity_key(row.supplier_ref) for row in leaf.supplier_alternatives} == (
        alternative_keys
    )
    assert (
        sum(
            row.requirement_gap_id == gap.requirement_gap_id
            for row in n7_pending_unique_derivation_source_gaps(bundle)
        )
        == 1
    )
    for snapshot in alternatives:
        assert _validate_supplier(case, gap, snapshot) == first["entry"].target_variable

    # The previous selected bundle binds both declarations and may not be read
    # after either is removed. A new plan may select the surviving declaration.
    for removed, survivor in ((first, second), (second, first)):
        blob_path, _manifest_path = store._paths(removed["ref"].artifact_id)
        original_bytes = blob_path.read_bytes()
        original_mode = stat.S_IMODE(blob_path.stat().st_mode)
        blob_path.unlink()
        try:
            with pytest.raises(ValueError, match=r"^n7_derivation_input_profile_unverified$"):
                load_n7_derivation_bundle(store, selected_ref)
            replanned_ref = fixture_owner._resolve(case, selection)
            assert type(replanned_ref) is ArtifactRef
            replanned, remaining_leaf, remaining_gap = fixture_owner._role_gap(
                case, replanned_ref, "denominator"
            )
            assert replanned.input_closure_status == "partial"
            assert replanned.target_satisfaction_status == "unsatisfied"
            assert tuple(
                artifact_ref_identity_key(row.supplier_ref)
                for row in remaining_leaf.supplier_alternatives
            ) == (artifact_ref_identity_key(survivor["ref"]),)
            assert (
                sum(
                    row.requirement_gap_id == remaining_gap.requirement_gap_id
                    for row in n7_pending_unique_derivation_source_gaps(replanned)
                )
                == 1
            )
            assert _validate_supplier(case, remaining_gap, survivor) == (
                first["entry"].target_variable
            )
        finally:
            blob_path.write_bytes(original_bytes)
            os.chmod(blob_path, original_mode)

        assert blob_path.read_bytes() == original_bytes
        fresh = FileSystemCAS.open_existing_read_only(store.root)
        assert load_n7_derivation_bundle(fresh, selected_ref) == bundle

    restored_ref = fixture_owner._resolve(case, selection)
    assert type(restored_ref) is ArtifactRef
    assert load_n7_derivation_bundle(store, restored_ref) == bundle
