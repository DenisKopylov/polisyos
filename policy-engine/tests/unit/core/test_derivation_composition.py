"""Compatibility and epistemic controls for opt-in certified composition."""

from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core import derivations as d


def _ref(store: artifacts.FileSystemCAS, label: str) -> artifacts.ArtifactRef:
    return store.put_json(
        {"label": label},
        artifacts.PutOptions(
            kind="test.derivation.evidence",
            media_type="application/json",
            schema=artifacts.SchemaInfo(name="test.derivation.evidence", version="1.0.0"),
            producer=artifacts.ProducerInfo(component="test.derivation", version="1.0.0"),
        ),
        return_selected_profile=True,
    )


def _selected(store: artifacts.FileSystemCAS, ref: artifacts.ArtifactRef) -> artifacts.ArtifactRef:
    manifest = store.get_manifest(ref)
    return store.put_bytes(
        store.get_bytes(ref),
        artifacts.PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            inputs=manifest.inputs,
            canon=manifest.canon,
        ),
        return_selected_profile=True,
    )


def _family(*, kinds: tuple[str, ...] = ("source",)) -> d.TransformFamily:
    return d.TransformFamily.model_validate(
        {
            "family_id": "identity",
            "method_id": "test.identity",
            "method_version": "1.0.0",
            "input_specs": (
                {
                    "role": "value",
                    "basis": {"quantity_kind": "ratio", "unit": "ratio"},
                    "allowed_input_kinds": kinds,
                },
            ),
            "output_basis": {"quantity_kind": "ratio", "unit": "ratio"},
            "year_domain_role": "value",
            "expression": {"operator": "current_value", "role": "value"},
            "assumption_rules": ({"name": "year_join", "literal_value": "exact"},),
        }
    )


def test_historical_source_only_abi_field_is_absent() -> None:
    family = _family()
    wire = family.model_dump(mode="json")
    assert "allowed_input_kinds" not in wire["input_specs"][0]
    legacy = {
        **wire,
        "input_specs": (
            {
                "role": "value",
                "basis": {"quantity_kind": "ratio", "unit": "ratio", "attributes": ()},
                "value_constraints": (),
            },
        ),
    }
    assert d._canonical_bytes(family) == d._canonical_bytes(legacy)
    assert d.TransformFamily.model_validate(wire) == family


def test_candidate_real_cas_wire_roundtrip_and_unknown_score(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    context = d.DerivationContext(
        context_ref=_ref(store, "context"), scope_ref=_ref(store, "scope"), years=(2020,)
    )
    source = d.CandidateSourceSeries(
        variable_id="candidate",
        basis=d.BasisSignature(quantity_kind="ratio", unit="ratio"),
        points=(d.SeriesPoint(year=2020, value=Decimal("0.2")),),
        source_occurrence_ref=_ref(store, "occurrence"),
        source_ref=_ref(store, "source"),
        context_ref=context.context_ref,
        scope_ref=context.scope_ref,
        lineage_refs=(_ref(store, "lineage"),),
        limitations=("caller_override",),
    )
    source_ref = d.persist_candidate_source_series(store, source)
    assert (
        d.CandidateSourceSeries.model_validate(artifacts.load_core_json_artifact(store, source_ref))
        == source
    )
    registry = d.TransformFamilyRegistry(families=(_family(kinds=("candidate_source",)),))
    registry_ref = d.persist_transform_family_registry(store, registry)
    assert registry_ref.manifest_profile_sha256
    assert store.get_manifest(registry_ref).artifact_schema.version == "3.0.0"
    recipe = d.build_composition_recipe(
        store,
        registry=registry,
        registry_ref=registry_ref,
        input_refs={"value": d.CandidateDerivationInput(artifact_ref=source_ref)},
        context=context,
        output_variable_id="result",
        family_id="identity",
    )
    materialized = d.materialize_composition(store, recipe)
    assert materialized.series.points == source.points
    assert materialized.series.evidence_status == "not_established"
    assert "effective_score" not in materialized.series.model_dump(mode="json")
    assert "effective_score" not in materialized.certificate.model_dump(mode="json")
    assert "source_value_correspondence_not_established" in materialized.series.limitations
    reader = artifacts.FileSystemCAS.open_existing_read_only(tmp_path / "cas")
    replayed = d.resolve_certified_composition(
        reader,
        certificate_ref=materialized.certificate_artifact_ref,
        consumer_method_id="test.fresh",
    )
    assert replayed.series == materialized.series
    assert d.materialize_composition(store, recipe).cache_hit


def test_legacy_declared_ceiling_does_not_promote_v3_empirical_authority(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    authority, verifier = _ref(store, "authority"), _ref(store, "verifier")
    source = d.SourceSeries(
        variable_id="source",
        basis=d.BasisSignature(quantity_kind="ratio", unit="ratio"),
        points=(d.SeriesPoint(year=2020, value=Decimal("0.2")),),
        authority=d.AuthorityProjection(
            effective_score=Decimal("0.9"),
            authority_ref=authority.artifact_id,
            verifier_provenance_ref=verifier.artifact_id,
            authoritative_for="series_input",
        ),
        observation_class="observed",
    )
    source_ref = _selected(store, d.persist_source_series(store, source))
    registry = d.TransformFamilyRegistry(families=(_family(),))
    registry_ref = _selected(store, d.persist_transform_family_registry(store, registry))
    assert store.get_manifest(registry_ref).artifact_schema.version == "2.0.0"
    context = d.DerivationContext(
        context_ref=_ref(store, "context"), scope_ref=_ref(store, "scope"), years=(2020,)
    )
    recipe = d.build_composition_recipe(
        store,
        registry=registry,
        registry_ref=registry_ref,
        input_refs={"value": d.SourceDerivationInput(artifact_ref=source_ref)},
        context=context,
        output_variable_id="result",
        family_id="identity",
    )
    result = d.materialize_composition(store, recipe)
    contribution = result.certificate.input_contributions[0]
    assert contribution.declared_ceiling == Decimal("0.9")
    assert contribution.authority_predicate_class == "consumer_asserted"
    assert result.series.evidence_status == "not_established"
    assert "effective_score" not in result.certificate.model_dump(mode="json")
    legacy_recipe = d.build_derivation_recipe(
        store,
        registry=registry,
        registry_ref=registry_ref,
        input_refs={"value": source_ref},
        output_variable_id="legacy",
        family_id="identity",
    )
    legacy = d.materialize_derivation(store, legacy_recipe)
    assert legacy.certificate.effective_authority == Decimal("0.9")
    assert (
        d.resolve_certified_derivation(
            store, certificate_ref=legacy.certificate_artifact_ref, consumer_method_id="test.legacy"
        ).series
        == legacy.series
    )


def test_v3_selected_input_rejects_profileless_wire() -> None:
    with pytest.raises(ValueError, match="selected manifest"):
        d.SourceDerivationInput.model_validate(
            {
                "artifact_ref": {
                    "artifact_id": "sha256:" + "a" * 64,
                    "kind": d.SOURCE_SERIES_KIND,
                    "media_type": "application/json",
                }
            }
        )


def _unit_bundle(
    store: artifacts.FileSystemCAS,
    *,
    label: str = "kilowatt hour",
    currency: str = "UAH",
    include_units: bool = True,
) -> artifacts.ArtifactRef:
    from polisyos.core.registry.builder import build_registry_bundle
    from polisyos.ir.kernel import (
        DEFAULT_CONSTRAINT_REGISTRY,
        DEFAULT_MECHANISM_REGISTRY,
        DEFAULT_MERGE_RULE_REGISTRY,
        DEFAULT_SLOT_REGISTRY,
        DEFAULT_UNITS_REGISTRY,
        GenericUnit,
        MoneyUnit,
        UnitsRegistry,
    )

    units = UnitsRegistry(
        units={
            **DEFAULT_UNITS_REGISTRY.units,
            "kwh": GenericUnit(label=label),
            "uah": MoneyUnit(currency=currency),
        }
    )
    return build_registry_bundle(
        store,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        units_registry=units if include_units else None,
        return_selected_profile=True,
    ).bundle_ref


def test_custom_model_unit_is_configured_data_and_foreign_definition_refuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    bundle_ref = _unit_bundle(store)
    context = d.DerivationContext(
        context_ref=_ref(store, "context"),
        scope_ref=_ref(store, "scope"),
        years=(2020,),
        units_profile="selected_registry_bundle",
        registry_bundle_ref=bundle_ref,
    )
    basis = d.BasisSignature(quantity_kind="energy", unit="kwh")
    source = d.CandidateSourceSeries(
        variable_id="energy",
        basis=basis,
        points=(d.SeriesPoint(year=2020, value=Decimal("3")),),
        source_occurrence_ref=_ref(store, "occurrence"),
        source_ref=_ref(store, "source"),
        context_ref=context.context_ref,
        scope_ref=context.scope_ref,
        lineage_refs=(_ref(store, "lineage"),),
        units_profile=context.units_profile,
        registry_bundle_ref=bundle_ref,
    )
    source_ref = d.persist_candidate_source_series(store, source)
    data = _family(kinds=("candidate_source",)).model_dump(mode="python")
    data["input_specs"] = (
        {"role": "value", "basis": basis, "allowed_input_kinds": ("candidate_source",)},
    )
    data["output_basis"] = basis
    data["expression"] = {
        "operator": "multiply",
        "operands": (
            {"operator": "current_value", "role": "value"},
            {"operator": "constant", "constant_value": "2"},
        ),
    }
    registry = d.load_transform_family_registry(
        {"families": (data,)}, store=store, registry_bundle_ref=bundle_ref
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
        output_variable_id="double_energy",
        family_id="identity",
    )
    result = d.materialize_composition(store, recipe)
    assert result.series.points[0].value == Decimal("6")
    reader = artifacts.FileSystemCAS.open_existing_read_only(tmp_path / "cas")
    assert (
        d.resolve_certified_composition(
            reader,
            certificate_ref=result.certificate_artifact_ref,
            consumer_method_id="custom.unit",
        ).series
        == result.series
    )
    from polisyos.ir.kernel import GenericUnit, UnitsRegistry

    with monkeypatch.context() as patch:
        unrelated_change = UnitsRegistry(
            units={
                **d._DEFAULT_UNITS_REGISTRY.units,
                "per_step": GenericUnit(label="unrelated changed unit"),
            }
        )
        patch.setattr(d, "_DEFAULT_UNITS_REGISTRY", unrelated_change)
        assert (
            d.resolve_certified_composition(
                reader,
                certificate_ref=result.certificate_artifact_ref,
                consumer_method_id="selected.only",
            ).series
            == result.series
        )
    changed_bundle = _unit_bundle(store, label="foreign same-named energy")
    changed_context = d.DerivationContext.model_validate(
        {**context.model_dump(mode="python"), "registry_bundle_ref": changed_bundle}
    )
    changed_registry = d.persist_transform_family_registry(
        store, registry, registry_bundle_ref=changed_bundle
    )
    assert changed_registry.artifact_id == registry_ref.artifact_id
    assert changed_registry.manifest_profile_sha256 != registry_ref.manifest_profile_sha256
    with pytest.raises(d.DerivationRefusalError, match="unit registry differs"):
        d.build_composition_recipe(
            store,
            registry=registry,
            registry_ref=changed_registry,
            input_refs={"value": d.CandidateDerivationInput(artifact_ref=source_ref)},
            context=changed_context,
            output_variable_id="double_energy",
            family_id="identity",
        )


@pytest.mark.parametrize("currency", ["UAH", "EUR"])
def test_legacy_source_unit_definition_is_reconciled(tmp_path: Path, currency: str) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    authority, verifier = _ref(store, "authority"), _ref(store, "verifier")
    basis = d.BasisSignature(quantity_kind="money", unit="uah")
    source = d.SourceSeries(
        variable_id="money",
        basis=basis,
        points=(d.SeriesPoint(year=2020, value=Decimal("3")),),
        authority=d.AuthorityProjection(
            effective_score=Decimal("0.9"),
            authority_ref=authority.artifact_id,
            verifier_provenance_ref=verifier.artifact_id,
            authoritative_for="series_input",
        ),
        observation_class="observed",
    )
    source_ref = d.persist_source_series(store, source, return_selected_profile=True)
    bundle_ref = _unit_bundle(store, currency=currency)
    context = d.DerivationContext(
        context_ref=_ref(store, "context"),
        scope_ref=_ref(store, "scope"),
        years=(2020,),
        units_profile="selected_registry_bundle",
        registry_bundle_ref=bundle_ref,
    )
    data = _family().model_dump(mode="python")
    data["input_specs"] = ({"role": "value", "basis": basis},)
    data["output_basis"] = basis
    registry = d.TransformFamilyRegistry(families=(d.TransformFamily.model_validate(data),))
    registry_ref = d.persist_transform_family_registry(
        store, registry, registry_bundle_ref=bundle_ref
    )
    assert store.get_manifest(registry_ref).artifact_schema.version == "3.0.0"
    if currency == "EUR":
        with pytest.raises(d.DerivationRefusalError, match="legacy source unit definition differs"):
            d.build_composition_recipe(
                store,
                registry=registry,
                registry_ref=registry_ref,
                input_refs={"value": d.SourceDerivationInput(artifact_ref=source_ref)},
                context=context,
                output_variable_id="money",
                family_id="identity",
            )
    else:
        recipe = d.build_composition_recipe(
            store,
            registry=registry,
            registry_ref=registry_ref,
            input_refs={"value": d.SourceDerivationInput(artifact_ref=source_ref)},
            context=context,
            output_variable_id="money",
            family_id="identity",
        )
        result = d.materialize_composition(store, recipe)
        reader = artifacts.FileSystemCAS.open_existing_read_only(tmp_path / "cas")
        assert (
            d.resolve_certified_composition(
                reader,
                certificate_ref=result.certificate_artifact_ref,
                consumer_method_id="legacy.units",
            ).series
            == result.series
        )


def test_builtin_unit_profile_is_content_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.ir.kernel import GenericUnit, UnitsRegistry

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    context = d.DerivationContext(
        context_ref=_ref(store, "context"), scope_ref=_ref(store, "scope"), years=(2020,)
    )
    changed = UnitsRegistry(
        units={**d._DEFAULT_UNITS_REGISTRY.units, "ratio": GenericUnit(label="foreign")}
    )
    monkeypatch.setattr(d, "_DEFAULT_UNITS_REGISTRY", changed)
    with pytest.raises(ValueError, match="unit definitions drifted"):
        d.DerivationContext.model_validate(context.model_dump(mode="python"))


@pytest.mark.parametrize("v3_first", [False, True])
def test_v2_and_v3_registry_producers_are_write_order_independent(
    tmp_path: Path, v3_first: bool
) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    registry = d.TransformFamilyRegistry(families=(_family(),))
    bundle_ref = _unit_bundle(store)
    if v3_first:
        v3_ref = d.persist_transform_family_registry(
            store, registry, registry_bundle_ref=bundle_ref
        )
        v2_ref = d.persist_transform_family_registry(store, registry)
    else:
        v2_ref = d.persist_transform_family_registry(store, registry)
        v3_ref = d.persist_transform_family_registry(
            store, registry, registry_bundle_ref=bundle_ref
        )
    assert v2_ref.artifact_id != v3_ref.artifact_id
    assert store.get_manifest(v2_ref).artifact_schema.version == "2.0.0"
    assert store.get_manifest(v3_ref).artifact_schema.version == "3.0.0"
    authority, verifier = _ref(store, "authority"), _ref(store, "verifier")
    source = d.SourceSeries(
        variable_id="ratio",
        basis=d.BasisSignature(quantity_kind="ratio", unit="ratio"),
        points=(d.SeriesPoint(year=2020, value=Decimal("0.2")),),
        authority=d.AuthorityProjection(
            effective_score=Decimal("0.9"),
            authority_ref=authority.artifact_id,
            verifier_provenance_ref=verifier.artifact_id,
            authoritative_for="series_input",
        ),
        observation_class="observed",
    )
    source_ref = d.persist_source_series(store, source, return_selected_profile=True)
    legacy_recipe = d.build_derivation_recipe(
        store,
        registry=registry,
        input_refs={"value": source_ref},
        output_variable_id="legacy",
        family_id="identity",
    )
    legacy = d.materialize_derivation(store, legacy_recipe)
    context = d.DerivationContext(
        context_ref=_ref(store, "context"),
        scope_ref=_ref(store, "scope"),
        years=(2020,),
        units_profile="selected_registry_bundle",
        registry_bundle_ref=bundle_ref,
    )
    recipe = d.build_composition_recipe(
        store,
        registry=registry,
        registry_ref=v3_ref,
        input_refs={"value": d.SourceDerivationInput(artifact_ref=source_ref)},
        context=context,
        output_variable_id="v3",
        family_id="identity",
    )
    current = d.materialize_composition(store, recipe)
    reader = artifacts.FileSystemCAS.open_existing_read_only(tmp_path / "cas")
    assert (
        d.resolve_certified_derivation(
            reader,
            certificate_ref=legacy.certificate_artifact_ref,
            consumer_method_id="legacy.order",
        ).series
        == legacy.series
    )
    assert (
        d.resolve_certified_composition(
            reader, certificate_ref=current.certificate_artifact_ref, consumer_method_id="v3.order"
        ).series
        == current.series
    )


def test_selected_model_profile_refuses_absent_unit_registry(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    bundle_ref = _unit_bundle(store, include_units=False)
    with pytest.raises(d.DerivationRefusalError, match="units registry cannot be reconciled"):
        d.load_transform_family_registry(
            {"families": (_family().model_dump(mode="python"),)},
            store=store,
            registry_bundle_ref=bundle_ref,
        )


def test_selected_unit_member_must_equal_exact_bundle_manifest_edge(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    bundle_ref = _unit_bundle(store)
    payload = artifacts.load_core_json_artifact(store, bundle_ref)
    units_ref = artifacts.ArtifactRef.model_validate(payload["units_registry"])
    manifest = store.get_manifest(units_ref)
    foreign_profile = store.put_bytes(
        store.get_bytes(units_ref),
        artifacts.PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            inputs=manifest.inputs,
            canon=manifest.canon,
            env=artifacts.EnvInfo(
                python="foreign-selected-profile",
                platform="fixture",
                deps_lock_hash="sha256:" + "a" * 64,
            ),
        ),
        return_selected_profile=True,
    )
    assert foreign_profile.artifact_id == units_ref.artifact_id
    assert foreign_profile.manifest_profile_sha256 != units_ref.manifest_profile_sha256
    bundle_manifest = store.get_manifest(bundle_ref)
    forged_bundle = store.put_json(
        {**payload, "units_registry": foreign_profile},
        artifacts.PutOptions(
            kind=bundle_manifest.kind,
            media_type=bundle_manifest.media_type,
            schema=bundle_manifest.artifact_schema,
            producer=bundle_manifest.producer,
            inputs=bundle_manifest.inputs,
            canon=bundle_manifest.canon,
        ),
        return_selected_profile=True,
    )
    with pytest.raises(d.DerivationRefusalError, match="units registry cannot be reconciled"):
        d.load_transform_family_registry(
            {"families": (_family().model_dump(mode="python"),)},
            store=store,
            registry_bundle_ref=forged_bundle,
        )
