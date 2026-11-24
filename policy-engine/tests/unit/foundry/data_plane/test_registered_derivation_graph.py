"""A registered two-edge relation supplies exactly one real Foundry input."""

from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.core import artifacts
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import (
    SelectedVariableBindingRef,
    load_model_input_obligation_set,
    load_resolved_input_binding_manifest,
    load_variable_representation,
)
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.core.contracts.semantic_composition_binding import (
    RegisteredDerivationRoleBasis,
    RegisteredSemanticBasis,
    load_registered_derived_graph_correspondence,
    persist_registered_derived_input_profile,
)
from polisyos.core.derivations import (
    DerivationRefusalError,
    TransformFamilyRegistry,
    load_composition_recipe_artifact,
    load_selected_transform_family_registry,
    persist_transform_family_registry,
)
from polisyos.data_forge.read_api import catalog
from polisyos.foundry.data_plane import replay_selected_method_input_facts
from polisyos.foundry.data_plane.bindings import prepare_registered_derivation_graph_inputs
from polisyos.runtime.quality import acquisition_planner as planner
from polisyos.runtime.quality import acquisition_world_growth as owner
from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
from polisyos.runtime.quality.model_input_routing import (
    RegisteredDerivedGraphModelInputRequest,
    materialize_registered_derived_model_inputs,
)
from polisyos.runtime.quality.n7_registered_derivation_plan import (
    persist_registered_n7_derivation_plan,
)
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
from tests.unit.core.contracts.test_semantic_derived_binding import _definition, _representation
from tests.unit.foundry.data_plane.test_selected_method_input_bindings import _removed_blob
from tests.unit.runtime.quality.test_n7_derivation_bundle import _pending_source, _target_gap
from tests.unit.runtime.quality.test_n7_registered_derivation_plan import (
    prepare_selected_plan_case,
)


def _replace_selected_json(store, ref, value, *, parent=None):
    manifest = store.get_manifest(ref)
    assert manifest.canon is not None
    inputs = manifest.inputs
    if parent is not None:
        role, selected = parent
        assert sum(edge.role == role for edge in inputs) == 1
        inputs = [
            artifacts.input_ref_from_artifact_ref(selected, role=role)
            if edge.role == role
            else edge
            for edge in inputs
        ]
    new_ref = store.put_json(
        value,
        artifacts.PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            producer=manifest.producer,
            inputs=inputs,
        ),
        canon_spec=CanonSpec(**manifest.canon.model_dump(mode="python")),
        return_selected_profile=True,
    )
    assert store.verify(new_ref).ok
    return new_ref


def _selected_registrations(setup, *, reverse):
    case = setup["case"]
    store = case.store
    profile = setup["profile"]
    role_bases = {row.role: row.basis for row in profile.inputs}
    source_c_ratio = role_bases[profile.ratio_role]
    intermediate = role_bases[profile.denominator_role]
    b_representation = load_variable_representation(store, intermediate.representation_ref)
    a_definition, _ = _definition(store, "annual-a")
    a_representation, _ = _representation(
        store, a_definition, population="all-public-expenditure", money=b_representation.money_unit
    )
    a_to_b_definition, _ = _definition(store, "annual-share-b-of-a")
    b_over_a_representation, _ = _representation(
        store,
        a_to_b_definition,
        population=b_representation.population_ref,
        money=b_representation.money_unit,
        numerator_ref=a_definition if reverse else intermediate.semantic_definition_ref,
        denominator_ref=intermediate.semantic_definition_ref if reverse else a_definition,
    )
    sources = {
        "a": RegisteredSemanticBasis(
            semantic_definition_ref=a_definition,
            representation_ref=a_representation,
            binding_profile_ref=intermediate.binding_profile_ref,
        ),
        "b_over_a": RegisteredSemanticBasis(
            semantic_definition_ref=a_to_b_definition,
            representation_ref=b_over_a_representation,
            binding_profile_ref=intermediate.binding_profile_ref,
        ),
        "c_over_b": source_c_ratio,
    }
    (family,) = load_selected_transform_family_registry(store, profile.registry_ref).families
    family_b = family.model_copy(update={"family_id": "test.annual.b", "method_id": "annual_b"})
    family_c = family.model_copy(
        update={
            "family_id": "test.annual.c",
            "method_id": "annual_c",
            "input_specs": tuple(
                item.model_copy(update={"allowed_input_kinds": ("certified_derived",)})
                if item.role == profile.denominator_role
                else item
                for item in family.input_specs
            ),
        }
    )
    registry_ref = persist_transform_family_registry(
        store,
        TransformFamilyRegistry(families=(family_b, family_c)),
        registry_bundle_ref=case.registry_bundle_ref,
    )
    selected_registry = SelectedVariableBindingRef.model_validate(
        registry_ref.model_dump(mode="python")
    )
    profile_b = profile.model_copy(
        update={
            "registry_ref": selected_registry,
            "family_id": family_b.family_id,
            "inputs": (
                RegisteredDerivationRoleBasis(role=profile.denominator_role, basis=sources["a"]),
                RegisteredDerivationRoleBasis(role=profile.ratio_role, basis=sources["b_over_a"]),
            ),
            "output": intermediate,
        }
    )
    profile_c = profile.model_copy(
        update={"registry_ref": selected_registry, "family_id": family_c.family_id}
    )
    return (
        sources,
        (profile_b, persist_registered_derived_input_profile(store, profile_b)),
        (profile_c, persist_registered_derived_input_profile(store, profile_c)),
    )


def _native_collection(tmp_path, setup, *, foreign_scope, reverse):
    case = setup["case"]
    store = case.store
    port = setup["target"].port
    source_bases, (profile_b, ref_b), (profile_c, ref_c) = _selected_registrations(
        setup, reverse=reverse
    )
    country_code = "PL" if foreign_scope else "UA"
    # Binary-exact ratios keep the expected decimal independent of float input conversion.
    values = {"a": 20_000_000_000, "b_over_a": 0.5, "c_over_b": -0.25}
    specs = []
    for node_id, source in source_bases.items():
        representation = load_variable_representation(store, source.representation_ref)
        unit = representation.unit_id
        is_ratio = unit == "ratio"
        specs.append(
            {
                "target_variable": f"fixture.{node_id}",
                "raw_field": node_id,
                "raw_unit": unit,
                "canonical_unit": unit,
                "unit_transform_ref": f"fabric://units/{unit}-identity/v1",
                "valid_min": -1 if is_ratio else 0,
                "valid_max": 1 if is_ratio else 300_000_000_000,
                "source_measure_scope": {
                    "population": representation.population_ref,
                    "temporal_granularity": representation.temporal_granularity,
                    "jurisdiction_ref": port.scope.jurisdiction_ref,
                    "time_period_basis": "calendar_year",
                    "source_geography_id": country_code,
                    "geography_ref": "country:PL" if foreign_scope else port.scope.geography_ref,
                },
                "source_semantic_definition_ref": source.semantic_definition_ref,
                "source_representation_ref": source.representation_ref,
            }
        )
    native = make_native_multivariable_active_projections(
        tmp_path / "native",
        source_rows=[{"country_code": country_code, "year": 2024, **values, "condition_json": {}}],
        variable_specs=specs,
        artifact_store=store,
        return_selected_raw_profile=True,
    )
    try:

        def n7_basis(basis):
            return planner.N7DerivationBasis.model_validate(basis.model_dump(mode="python"))

        planned_leaves = []
        source_inputs = []
        for entry in native.entries:
            node_id = entry.raw_field
            supplier = catalog.persist_acquisition_supplier_declaration(
                store, native.authority, entry_id=entry.entry_id
            )
            planned_leaves.append(
                _pending_source(
                    node_id,
                    n7_basis(source_bases[node_id]),
                    _target_gap(setup["target"].context, entry.target_variable),
                    alternatives=(supplier,),
                )
            )
            projection = native.projections[entry.target_variable]
            (item,) = projection.observations
            passport = AdmissionPassport.model_validate(
                epoch_contract.load_verified_epoch_statement(
                    store=store,
                    ref=projection.passport_ref,
                    expected_kind="epoch.acquisition_passport_snapshot",
                )
            )
            source_inputs.append(
                owner.NativeDerivationSourceInput(
                    source_node_id=node_id,
                    supplier_ref=supplier,
                    overlay=native.overlay,
                    receipt_ref=projection.receipt_ref,
                    passport=passport,
                    observation_id=item.observation.observation_id,
                )
            )

        def operation(node_id, profile, ref, inputs):
            return planner.N7DerivationOperationNode(
                node_id=node_id,
                registered_profile_ref=ref,
                operator_ref=profile.registry_ref,
                family_id=profile.family_id,
                method_version=profile.method_version,
                output_basis=n7_basis(profile.output),
                role_inputs=tuple(
                    planner.N7DerivationRoleInput(
                        role=row.role, input_node_id=input_id, source_basis=n7_basis(row.basis)
                    )
                    for row, input_id in zip(profile.inputs, inputs, strict=True)
                ),
            )

        bundle_ref = persist_registered_n7_derivation_plan(
            store,
            routing_report_ref=setup["routing_ref"],
            obligation_set_ref=setup["obligation_set_ref"],
            target_obligation_ref=setup["target_ref"],
            registered_profile_ref=ref_c,
            dag_budget_profile_ref=setup["budget_ref"],
            source_nodes=tuple(planned_leaves),
            operation_nodes=(
                operation("derived-b", profile_b, ref_b, ("a", "b_over_a")),
                operation("derived-c", profile_c, ref_c, ("derived-b", "c_over_b")),
            ),
            root_node_id="derived-c",
        )
        collection = owner.collect_native_derivation_inputs(
            store,
            derivation_bundle_ref=bundle_ref,
            source_inputs=tuple(source_inputs),
            authority=native.authority,
        )
        return RegisteredDerivedGraphModelInputRequest(
            model_input_obligation_ref=setup["target_ref"],
            profile_ref=ref_c,
            collection_ref=owner.persist_native_derivation_input_collection(store, collection),
            binding_id="selected-c",
        )
    finally:
        native.overlay.close()


@pytest.mark.parametrize(
    ("foreign_scope", "reverse", "refusal"),
    [
        (False, False, None),
        (True, False, "composition_input_native_role_context_mismatch"),
        (False, True, "registered_ratio_role_semantics_mismatch"),
    ],
    ids=("verified-root", "same-value-disjoint-geography", "reverse-relation"),
)
def test_registered_graph_persists_only_the_verified_root(
    tmp_path, monkeypatch, foreign_scope, reverse, refusal
):
    setup = prepare_selected_plan_case(
        tmp_path / "root", role_populations={"denominator": "public-health-expenditure"}
    )
    case = setup["case"]
    try:
        request = _native_collection(tmp_path, setup, foreign_scope=foreign_scope, reverse=reverse)
        args = {
            "base_data_snapshot_ref": case.data_snapshot_ref,
            "obligation_set_ref": setup["obligation_set_ref"],
            "inputs": (request,),
        }
        if refusal is not None:

            def unexpected(*args, **kwargs):
                pytest.fail("A refused semantic graph attempted arithmetic")

            monkeypatch.setattr("polisyos.core.derivations.materialize_derivation_dag", unexpected)
            with pytest.raises(ValueError, match=refusal):
                materialize_registered_derived_model_inputs(case.store, **args)
            return

        batch = materialize_registered_derived_model_inputs(case.store, **args)
        reader = artifacts.FileSystemCAS.open_existing_read_only(case.store.root)
        selected_set, _ = load_model_input_obligation_set(reader, setup["obligation_set_ref"])
        manifest = load_resolved_input_binding_manifest(reader, batch.resolved_binding_manifest_ref)
        (selection,) = manifest.derivations
        assert selection.model_port_id == setup["target"].port.port_id
        assert selection.binding_id == "selected-c"
        proof = load_registered_derived_graph_correspondence(reader, selection.correspondence_ref)
        assert proof.root.node_id == "derived-c"
        b, c = proof.operations
        assert b.node_id == "derived-b"
        c_recipe = load_composition_recipe_artifact(reader, c.recipe_ref)
        (denominator, _) = c_recipe.inputs
        assert denominator.kind == "certified_derived"
        assert denominator.artifact.artifact_id == b.output_ref.artifact_id
        assert denominator.certificate is not None
        assert denominator.certificate.artifact_id == b.certificate_ref.artifact_id
        b_series = artifacts.load_core_json_artifact(reader, b.output_ref)
        assert Decimal(b_series["points"][0]["value"]) == Decimal("10000000000")

        def selected_facts():
            return replay_selected_method_input_facts(
                reader,
                input_bindings_ref=batch.input_bindings_ref,
                expected_invocation=selected_set.invocation,
            )

        (foundry_input,) = selected_facts().records
        assert foundry_input.port_id == selection.model_port_id
        assert foundry_input.canonical_value == Decimal("-2500000000")
        for ref in (b.recipe_ref, b.certificate_ref):
            with (
                _removed_blob(case.store, ref),
                pytest.raises((DerivationRefusalError, FileNotFoundError)),
            ):
                selected_facts()
        collection = owner.replay_native_derivation_input_collection(
            reader, request.collection_ref
        ).collection
        supplier = collection.source_inputs[0].supplier_ref
        view = case.store._manifest_path_for_ref(
            supplier.artifact_id, supplier.manifest_profile_sha256
        )
        blob, default_view = case.store._paths(supplier.artifact_id)
        held = view.with_suffix(".held")
        view.rename(held)
        try:
            assert blob.is_file() and default_view.is_file()
            with pytest.raises(
                catalog.AcquisitionAuthorityError,
                match="supplier_declaration_selected_ref_unavailable",
            ):
                selected_facts()
        finally:
            held.rename(view)
        assert selected_facts().records == (foundry_input,)

        graph_selection = {
            "collection_ref": request.collection_ref,
            "profile_ref": request.profile_ref,
            "obligation_set_ref": setup["obligation_set_ref"],
            "obligation_ref": setup["target_ref"],
            "obligation": setup["target"],
        }
        bundle = artifacts.load_core_json_artifact(reader, proof.bundle_ref)
        routing_ref = artifacts.ArtifactRef.model_validate(bundle["model_input_routing_report_ref"])
        routing = artifacts.load_core_json_artifact(reader, routing_ref)
        compilation_ref = artifacts.ArtifactRef.model_validate(routing["compilation_report_ref"])
        compilation = artifacts.load_core_json_artifact(reader, compilation_ref)
        (requirement,) = compilation["requirements"]
        assert requirement["scope"]["geography"] != "foreign-geography"
        wrong_scope = _replace_selected_json(
            case.store,
            compilation_ref,
            compilation
            | {
                "requirements": [
                    requirement
                    | {"scope": requirement["scope"] | {"geography": "foreign-geography"}}
                ]
            },
        )
        wrong_scope_routing = _replace_selected_json(
            case.store,
            routing_ref,
            routing | {"compilation_report_ref": wrong_scope.model_dump(mode="json")},
            parent=("model_input_compilation_report", wrong_scope),
        )
        (route,) = routing["routes"]
        assert route["disposition"] == "conflict" and route["query_envelope"]["rows"]
        false_absence = _replace_selected_json(
            case.store,
            routing_ref,
            routing
            | {
                "routes": [
                    route
                    | {
                        "disposition": "absent",
                        "reason_code": "model_input_source_descriptor_unresolved",
                    }
                ]
            },
        )
        for invalid_routing_ref, reason in (
            (wrong_scope_routing, "foundry_input_bindings_graph_routing_denominator_mismatch"),
            (false_absence, "foundry_input_bindings_graph_routing_absence_query_not_empty"),
        ):
            bad_bundle = _replace_selected_json(
                case.store,
                proof.bundle_ref,
                bundle
                | {"model_input_routing_report_ref": invalid_routing_ref.model_dump(mode="json")},
                parent=("selected_model_input_routing_report", invalid_routing_ref),
            )
            with pytest.raises(ValueError, match=reason):
                prepare_registered_derivation_graph_inputs(
                    reader, bundle_ref=bad_bundle, **graph_selection
                )

        bundle_manifest = reader.get_manifest(proof.bundle_ref)
        original_bundle = reader.get_bytes(proof.bundle_ref)
        for missing_role in ("operation.derived-b.operator", "source.a.definition"):
            inputs = [edge for edge in bundle_manifest.inputs if edge.role != missing_role]
            assert len(inputs) == len(bundle_manifest.inputs) - 1
            incomplete_view = case.store.put_bytes(
                original_bundle,
                artifacts.PutOptions(
                    kind=bundle_manifest.kind,
                    media_type=bundle_manifest.media_type,
                    schema=bundle_manifest.artifact_schema,
                    canon=bundle_manifest.canon,
                    producer=bundle_manifest.producer,
                    inputs=inputs,
                ),
                return_selected_profile=True,
            )
            assert incomplete_view.artifact_id == proof.bundle_ref.artifact_id
            assert (
                incomplete_view.manifest_profile_sha256 != proof.bundle_ref.manifest_profile_sha256
            )
            assert case.store.verify(incomplete_view).ok
            with pytest.raises(
                ValueError, match="foundry_input_bindings_graph_bundle_lineage_mismatch"
            ):
                prepare_registered_derivation_graph_inputs(
                    reader,
                    bundle_ref=incomplete_view,
                    **graph_selection,
                )
    finally:
        case.close()
