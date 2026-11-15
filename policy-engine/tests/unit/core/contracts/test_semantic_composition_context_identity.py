"""Live and reopened derivation contexts share identities, not Python brands."""

from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.core import artifacts
from polisyos.core import derivations as d
from polisyos.core.contracts.variable_binding import SelectedVariableBindingRef
from polisyos.core.derivations import _same_derivation_context
from tests.unit.core.test_derivation_composition import _family, _ref, _unit_bundle


@pytest.fixture(scope="module")
def materialized_contexts(tmp_path_factory):
    """Use an actual Core producer, selected unit bundle and fresh CAS reader."""
    root = tmp_path_factory.mktemp("composition-context-identity")
    store = artifacts.FileSystemCAS(root / "cas")

    def typed(ref):
        return SelectedVariableBindingRef.model_validate(ref.model_dump(mode="python"))

    bundle_ref = _unit_bundle(store)
    context = d.DerivationContext(
        context_ref=typed(_ref(store, "context")),
        scope_ref=typed(_ref(store, "scope")),
        years=(2020,),
        units_profile="selected_registry_bundle",
        registry_bundle_ref=typed(bundle_ref),
    )
    source = d.CandidateSourceSeries(
        variable_id="fixture.context-identity",
        basis=d.BasisSignature(quantity_kind="ratio", unit="ratio"),
        points=(d.SeriesPoint(year=2020, value=Decimal("0.2")),),
        source_occurrence_ref=_ref(store, "occurrence"),
        source_ref=_ref(store, "source"),
        context_ref=context.context_ref,
        scope_ref=context.scope_ref,
        units_profile=context.units_profile,
        registry_bundle_ref=context.registry_bundle_ref,
        lineage_refs=(_ref(store, "lineage"),),
    )
    source_ref = d.persist_candidate_source_series(store, source)
    registry = d.TransformFamilyRegistry(
        families=(_family(kinds=("candidate_source", "certified_derived")),)
    )
    registry_ref = d.persist_transform_family_registry(
        store, registry, registry_bundle_ref=bundle_ref
    )
    recipe = d.build_composition_recipe(
        store,
        registry=registry,
        registry_ref=registry_ref,
        input_refs={"value": d.CandidateDerivationInput(artifact_ref=source_ref)},
        context=context,
        output_variable_id="fixture.context-identity",
        family_id="identity",
    )
    recipe_ref = d.persist_composition_recipe_artifact(store, recipe)
    output = d.materialize_composition(store, recipe)
    fresh = artifacts.FileSystemCAS.open_existing_read_only(store.root)
    reopened_recipe = d.load_composition_recipe_artifact(fresh, recipe_ref)
    resolved = d.resolve_certified_composition(
        fresh,
        certificate_ref=output.certificate_artifact_ref,
        consumer_method_id="tests.context-identity",
    )
    assert resolved.series.points == (d.SeriesPoint(year=2020, value=Decimal("0.2")),)
    assert reopened_recipe.context == resolved.series.context
    return recipe.context, resolved.series.context, store, source, registry_ref, registry, output


def test_live_typed_refs_match_the_actual_materialized_context(materialized_contexts) -> None:
    original, reopened, *_ = materialized_contexts
    assert type(original.context_ref) is SelectedVariableBindingRef
    assert type(reopened.context_ref) is artifacts.ArtifactRef
    assert original != reopened
    assert original.model_dump(mode="json") == reopened.model_dump(mode="json")
    assert _same_derivation_context(original, reopened)
    assert _same_derivation_context(reopened, original)


def test_real_normalizer_rejects_another_selected_unit_bundle(materialized_contexts) -> None:
    original, _, store, source, registry_ref, registry, _ = materialized_contexts
    foreign_bundle = _unit_bundle(store, label="another selected unit definition")
    foreign_source = source.model_copy(update={"registry_bundle_ref": foreign_bundle})
    foreign_source_ref = d.persist_candidate_source_series(store, foreign_source)
    with pytest.raises(d.DerivationRefusalError, match="candidate unit registry differs"):
        d.build_composition_recipe(
            store,
            registry=registry,
            registry_ref=registry_ref,
            input_refs={"value": d.CandidateDerivationInput(artifact_ref=foreign_source_ref)},
            context=original,
            output_variable_id="fixture.context-identity",
            family_id="identity",
        )


def test_certified_child_keeps_the_live_context_identity(materialized_contexts) -> None:
    original, _, store, _, registry_ref, registry, parent = materialized_contexts
    child = d.build_composition_recipe(
        store,
        registry=registry,
        registry_ref=registry_ref,
        input_refs={
            "value": d.CertifiedDerivedInput(
                artifact_ref=parent.derived_artifact_ref,
                certificate_ref=parent.certificate_artifact_ref,
            )
        },
        context=original,
        output_variable_id="fixture.context-identity.child",
        family_id="identity",
    )
    child_output = d.materialize_composition(store, child)
    assert child_output.series.points == parent.series.points
    assert _same_derivation_context(child_output.series.context, original)


@pytest.mark.parametrize("field", ["context_ref", "scope_ref", "registry_bundle_ref"])
@pytest.mark.parametrize(
    "component", ["artifact_id", "kind", "media_type", "manifest_profile_sha256"]
)
def test_each_selected_reference_identity_field_is_load_bearing(
    materialized_contexts, field: str, component: str
) -> None:
    original, reopened, *_ = materialized_contexts
    ref = getattr(original, field)
    assert ref is not None
    mutations = {
        "artifact_id": artifacts.ArtifactID.from_sha256_hex("f" * 64),
        "kind": ref.kind + ".foreign",
        "media_type": "application/octet-stream",
        "manifest_profile_sha256": "sha256:" + "f" * 64,
    }
    changed = original.model_copy(
        update={field: ref.model_copy(update={component: mutations[component]})}
    )
    assert not _same_derivation_context(changed, reopened)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("years", (2021,)),
        ("units_profile", "builtin_v1"),
        ("builtin_units_sha256", "sha256:" + "a" * 64),
    ],
)
def test_context_semantic_values_are_not_normalized_away(
    materialized_contexts, field: str, value: object
) -> None:
    original, reopened, *_ = materialized_contexts
    # Deliberately corrupted objects must still fail the pure consumer predicate,
    # rather than becoming equal through reference normalization.
    changed = original.model_copy(update={field: value})
    assert not _same_derivation_context(changed, reopened)


def test_optional_registry_ref_requires_matching_presence(materialized_contexts) -> None:
    original, *_ = materialized_contexts
    builtin = d.DerivationContext(
        context_ref=original.context_ref, scope_ref=original.scope_ref, years=original.years
    )
    reopened = d.DerivationContext.model_validate(builtin.model_dump(mode="python"))
    assert builtin.registry_bundle_ref is reopened.registry_bundle_ref is None
    assert _same_derivation_context(builtin, reopened)
    grafted = builtin.model_copy(update={"registry_bundle_ref": original.registry_bundle_ref})
    assert not _same_derivation_context(grafted, reopened)


def test_new_serialized_context_metadata_remains_load_bearing(materialized_contexts) -> None:
    original, *_ = materialized_contexts

    class ExtendedContext(d.DerivationContext):
        context_metadata: tuple[tuple[str, str], ...]

    payload = original.model_dump(mode="python") | {
        "context_metadata": (("coordinate_rule", "annual.v1"),)
    }
    first = ExtendedContext.model_validate(payload)
    same = ExtendedContext.model_validate(first.model_dump(mode="python"))
    changed = first.model_copy(update={"context_metadata": (("coordinate_rule", "annual.v2"),)})
    assert _same_derivation_context(first, same)
    assert not _same_derivation_context(first, changed)
    assert not _same_derivation_context(first, original)
