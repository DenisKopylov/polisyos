"""Semantic tests for the data-defined derivation engine."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core import artifacts, canon
from polisyos.runtime.quality import derived_observations as derived_module
from polisyos.runtime.quality import epoch_validity_cascade as epoch_cascade
from polisyos.runtime.quality import semantic_epoch as semantic_epoch_runtime
from polisyos.runtime.quality.derived_observations import (
    ArithmeticExpression,
    AuthorityProjection,
    BasisAttribute,
    BasisSignature,
    DerivationRefusalCode,
    DerivationRefusalError,
    DerivationRefusalReason,
    SeriesPoint,
    SourceSeries,
    TransformFamily,
    TransformFamilyRegistry,
    build_derivation_recipe,
    consume_certified_derivation,
    load_transform_family_registry,
    materialize_derivation,
    persist_source_series,
    persist_transform_family_registry,
)


def _basis(
    quantity_kind: str,
    unit: str,
    **attributes: str,
) -> BasisSignature:
    return BasisSignature(
        quantity_kind=quantity_kind,
        unit=unit,
        attributes=tuple(
            BasisAttribute(name=name, value=value) for name, value in sorted(attributes.items())
        ),
    )


CURRENT_MONEY = _basis(
    "monetary_flow",
    "uah",
    currency="UAH",
    price_basis="current",
)
PRICE_LEVEL = _basis(
    "price_level",
    "ratio",
    reference_year="2010",
)
CONSTANT_MONEY = _basis(
    "monetary_flow",
    "uah",
    base_year="2020",
    currency="UAH",
    price_basis="constant",
)
PERCENT_SHARE = _basis(
    "share_of_total",
    "percent",
    denominator_basis="declared_total",
)
CURRENT_USD = _basis(
    "monetary_flow",
    "usd",
    currency="USD",
    price_basis="current",
)


def _leaf(operator: str, **fields: object) -> dict[str, object]:
    return {"operator": operator, **fields}


def _price_rebase_family_data() -> dict[str, object]:
    output_template = _basis(
        "monetary_flow",
        "uah",
        base_year="${base_year}",
        currency="UAH",
        price_basis="constant",
    )
    return {
        "family_id": "price_level_rebase",
        "method_id": "arithmetic.exact_year.price_level_rebase",
        "method_version": "1.0.0",
        "input_specs": (
            {"role": "amount", "basis": CURRENT_MONEY},
            {
                "role": "index",
                "basis": PRICE_LEVEL,
                "value_constraints": ("positive",),
            },
        ),
        "output_basis": output_template,
        "year_domain_role": "amount",
        "parameter_rules": (
            {
                "name": "base_year",
                "operator": "lower_median_common_year",
                "input_roles": ("amount", "index"),
            },
        ),
        "output_parameter_bindings": (
            {"parameter_name": "base_year", "output_attribute": "base_year"},
        ),
        "expression": {
            "operator": "divide",
            "operands": (
                {
                    "operator": "multiply",
                    "operands": (
                        _leaf("current_value", role="amount"),
                        _leaf(
                            "value_at_parameter",
                            role="index",
                            parameter_name="base_year",
                        ),
                    ),
                },
                _leaf("current_value", role="index"),
            ),
        },
        "assumption_rules": (
            {"name": "base_year", "parameter_name": "base_year"},
            {
                "name": "formula",
                "literal_value": "amount_t * index_base / index_t",
            },
            {"name": "source_reference_year", "literal_value": "2010"},
            {"name": "year_join", "literal_value": "exact; no interpolation"},
        ),
    }


def _percent_conversion_family_data() -> dict[str, object]:
    return {
        "family_id": "percent_of_total_conversion",
        "method_id": "arithmetic.exact_year.percent_times_total",
        "method_version": "1.0.0",
        "input_specs": (
            {"role": "share", "basis": PERCENT_SHARE},
            {"role": "total", "basis": CURRENT_USD},
        ),
        "output_basis": CURRENT_USD,
        "year_domain_role": "share",
        "parameter_rules": (),
        "output_parameter_bindings": (),
        "expression": {
            "operator": "divide",
            "operands": (
                {
                    "operator": "multiply",
                    "operands": (
                        _leaf("current_value", role="share"),
                        _leaf("current_value", role="total"),
                    ),
                },
                _leaf("constant", constant_value="100"),
            ),
        },
        "assumption_rules": (
            {
                "name": "formula",
                "literal_value": "share_t * total_t / 100",
            },
            {"name": "scale", "literal_value": "100 percent per whole"},
            {"name": "year_join", "literal_value": "exact; no interpolation"},
        ),
    }


def _registry(*extra: dict[str, object]) -> TransformFamilyRegistry:
    families = (
        _percent_conversion_family_data(),
        _price_rebase_family_data(),
        *extra,
    )
    return load_transform_family_registry(
        {
            "families": tuple(
                sorted(
                    families,
                    key=lambda item: (str(item["family_id"]), str(item["method_version"])),
                )
            )
        }
    )


def _evidence_ref(store: artifacts.FileSystemCAS, label: str) -> artifacts.ArtifactRef:
    return store.put_json(
        {"label": label},
        artifacts.PutOptions(
            kind="test.verifier_evidence",
            media_type="application/json",
            schema=artifacts.SchemaInfo(name="test.verifier-evidence", version="1.0.0"),
            producer=artifacts.ProducerInfo(
                component="polisyos.tests.derivation_verifier",
                version="1.0.0",
            ),
        ),
    )


def _authority(
    store: artifacts.FileSystemCAS,
    *,
    label: str,
    score: str,
) -> AuthorityProjection:
    authority = _evidence_ref(store, f"{label}-authority")
    verifier = _evidence_ref(store, f"{label}-verifier")
    return AuthorityProjection(
        effective_score=Decimal(score),
        authority_ref=authority.artifact_id,
        verifier_provenance_ref=verifier.artifact_id,
        authoritative_for="series_input",
    )


def _source_producer() -> artifacts.ProducerInfo:
    return artifacts.ProducerInfo(
        component="polisyos.runtime.quality.derived_observations",
        version="2.0.0",
    )


def _persist(
    store: artifacts.FileSystemCAS,
    *,
    role: str,
    basis: BasisSignature,
    values: tuple[tuple[int, str], ...],
    score: str,
) -> artifacts.ArtifactRef:
    return persist_source_series(
        store,
        SourceSeries(
            variable_id=f"test.{role}",
            basis=basis,
            points=tuple(SeriesPoint(year=year, value=Decimal(value)) for year, value in values),
            authority=_authority(store, label=role, score=score),
            observation_class="observed",
        ),
    )


def _case_inputs(
    root: Path,
    family_id: str,
) -> tuple[
    artifacts.FileSystemCAS,
    dict[str, artifacts.ArtifactRef],
    BasisSignature,
    tuple[Decimal, ...],
    Decimal,
]:
    store = artifacts.FileSystemCAS(root)
    if family_id == "price_level_rebase":
        refs = {
            "amount": _persist(
                store,
                role="amount",
                basis=CURRENT_MONEY,
                values=((2019, "100"), (2020, "220"), (2021, "360")),
                score="0.82",
            ),
            "index": _persist(
                store,
                role="index",
                basis=PRICE_LEVEL,
                values=((2019, "50"), (2020, "100"), (2021, "120")),
                score="0.71",
            ),
        }
        return (
            store,
            refs,
            CONSTANT_MONEY,
            (Decimal("200"), Decimal("220"), Decimal("300")),
            Decimal("0.71"),
        )
    refs = {
        "share": _persist(
            store,
            role="share",
            basis=PERCENT_SHARE,
            values=((2019, "-2"), (2020, "5"), (2021, "10")),
            score="0.64",
        ),
        "total": _persist(
            store,
            role="total",
            basis=CURRENT_USD,
            values=((2019, "1000"), (2020, "1200"), (2021, "900")),
            score="0.79",
        ),
    }
    return (
        store,
        refs,
        CURRENT_USD,
        (Decimal("-20"), Decimal("60"), Decimal("90")),
        Decimal("0.64"),
    )


@pytest.mark.parametrize(
    "family_id",
    ["percent_of_total_conversion", "price_level_rebase"],
)
def test_registered_families_share_recipe_cache_certificate_and_passport_boundary(
    tmp_path: Path,
    family_id: str,
) -> None:
    store, refs, output_basis, expected, authority = _case_inputs(
        tmp_path / family_id,
        family_id,
    )
    recipe = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id=f"test.output.{family_id}",
        output_basis=output_basis,
    )

    first = materialize_derivation(store, recipe)
    second = materialize_derivation(store, recipe)

    assert tuple(point.value for point in first.series.points) == expected
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.derived_artifact_ref == first.derived_artifact_ref
    assert second.certificate_artifact_ref == first.certificate_artifact_ref
    assert second.certificate.effective_authority == authority
    assert second.series.observation_class == "derived"
    assert second.certificate.observation_class == "derived"
    assert "observed_series" in second.certificate.may_not_use_for
    assert len(recipe.inputs) == len(refs)
    assert all(item.artifact.manifest_sha256.startswith("sha256:") for item in recipe.inputs)


def test_recipe_identity_excludes_only_manifest_created_at(tmp_path: Path) -> None:
    store, refs, output_basis, _, _ = _case_inputs(
        tmp_path / "cas",
        "percent_of_total_conversion",
    )
    first = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id="test.stable.manifest",
        output_basis=output_basis,
    )
    artifact_ids = (
        first.registry_artifact.artifact_id,
        *(item.artifact.artifact_id for item in first.inputs),
    )
    for artifact_id in artifact_ids:
        _, manifest_path = store.get_paths(artifact_id)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["created_at"] = "2035-01-02T03:04:05Z"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    second = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id="test.stable.manifest",
        output_basis=output_basis,
    )

    assert second == first


def _three_input_family_data(
    first: BasisSignature,
    second: BasisSignature,
    third: BasisSignature,
    output: BasisSignature,
) -> dict[str, object]:
    return {
        "family_id": "novel_three_input_family",
        "method_id": "arithmetic.exact_year.product_plus_offset",
        "method_version": "7.3.0",
        "input_specs": (
            {"role": "first", "basis": first},
            {"role": "second", "basis": second},
            {"role": "third", "basis": third},
        ),
        "output_basis": output,
        "year_domain_role": "first",
        "expression": {
            "operator": "add",
            "operands": (
                {
                    "operator": "multiply",
                    "operands": (
                        _leaf("current_value", role="first"),
                        _leaf("current_value", role="second"),
                    ),
                },
                _leaf("current_value", role="third"),
            ),
        },
        "assumption_rules": ({"name": "formula", "literal_value": "first * second + third"},),
    }


def _same_source_family_data() -> dict[str, object]:
    return {
        "family_id": "same_source_addition",
        "method_id": "arithmetic.exact_year.add",
        "method_version": "1.0.0",
        "input_specs": (
            {"role": "left", "basis": PERCENT_SHARE},
            {"role": "right", "basis": PERCENT_SHARE},
        ),
        "output_basis": PERCENT_SHARE,
        "year_domain_role": "left",
        "expression": {
            "operator": "add",
            "operands": (
                _leaf("current_value", role="left"),
                _leaf("current_value", role="right"),
            ),
        },
        "assumption_rules": ({"name": "formula", "literal_value": "left + right"},),
    }


def _forge_recipe_family(recipe: Any) -> Any:
    payload = recipe.model_dump(mode="python")
    payload["family"]["family_id"] = "unregistered_recomputed_family"
    identity_payload = {key: value for key, value in payload.items() if key != "recipe_id"}
    payload["recipe_id"] = derived_module._identity(
        "derivation-recipe",
        identity_payload,
    )
    return type(recipe).model_validate(payload)


def _persist_recipe_graph_without_public_intake(
    store: artifacts.FileSystemCAS,
    recipe: Any,
) -> artifacts.ArtifactRef:
    sources = derived_module._load_recipe_sources(
        store,
        recipe,
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    series = derived_module._derive_series(recipe, sources)
    derived_ref, _ = derived_module._put_or_verify(
        store,
        payload=series,
        kind=derived_module.DERIVED_SERIES_KIND,
        schema=derived_module._DERIVED_SERIES_SCHEMA,
        inputs=derived_module._expected_output_inputs(recipe),
        refusal_code=DerivationRefusalCode.CACHE_ARTIFACT_DRIFT,
    )
    certificate = derived_module._certificate(recipe, sources, derived_ref.artifact_id)
    certificate_ref, _ = derived_module._put_or_verify(
        store,
        payload=certificate,
        kind=derived_module.DERIVATION_CERTIFICATE_KIND,
        schema=derived_module._CERTIFICATE_SCHEMA,
        inputs=derived_module._expected_certificate_inputs(
            recipe,
            derived_ref.artifact_id,
        ),
        refusal_code=DerivationRefusalCode.CERTIFICATE_DRIFT,
    )
    return certificate_ref


def test_novel_family_is_typed_refused_then_accepted_by_registry_data_only(
    tmp_path: Path,
) -> None:
    first_basis = _basis("novel_first", "percent")
    second_basis = _basis("novel_second", "ratio")
    third_basis = _basis("novel_third", "usd")
    output_basis = _basis("novel_output", "ratio")
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    refs = {
        "first": _persist(
            store,
            role="first",
            basis=first_basis,
            values=((2020, "2"),),
            score="0.9",
        ),
        "second": _persist(
            store,
            role="second",
            basis=second_basis,
            values=((2020, "3"),),
            score="0.8",
        ),
        "third": _persist(
            store,
            role="third",
            basis=third_basis,
            values=((2020, "4"),),
            score="0.7",
        ),
    }

    with pytest.raises(DerivationRefusalError) as refused:
        build_derivation_recipe(
            store,
            registry=_registry(),
            input_refs=refs,
            output_variable_id="test.novel.output",
            output_basis=output_basis,
        )
    assert refused.value.code is DerivationRefusalCode.BASIS_MISMATCH
    assert refused.value.reason is DerivationRefusalReason.NO_CERTIFIED_TRANSFORM

    family_data = _three_input_family_data(
        first_basis,
        second_basis,
        third_basis,
        output_basis,
    )
    recipe = build_derivation_recipe(
        store,
        registry=_registry(family_data),
        input_refs=refs,
        output_variable_id="test.novel.output",
        output_basis=output_basis,
    )
    materialized = materialize_derivation(store, recipe)

    assert materialized.series.points[0].value == Decimal("10")
    assert len(recipe.inputs) == 3
    assert materialized.certificate.effective_authority == Decimal("0.7")


def test_same_source_artifact_can_fill_two_recipe_roles_and_replay(
    tmp_path: Path,
) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    source_ref = _persist(
        store,
        role="shared",
        basis=PERCENT_SHARE,
        values=((2020, "5"), (2021, "8")),
        score="0.8",
    )
    registry = _registry(_same_source_family_data())
    recipe = build_derivation_recipe(
        store,
        registry=registry,
        input_refs={"left": source_ref, "right": source_ref},
        output_variable_id="test.same.source",
        output_basis=PERCENT_SHARE,
        family_id="same_source_addition",
    )

    materialized = materialize_derivation(store, recipe)
    consumed = consume_certified_derivation(
        store,
        certificate_ref=materialized.certificate_artifact_ref,
        consumer_method_id="test.same.source.consumer@1.0.0",
    )

    assert tuple(point.value for point in materialized.series.points) == (
        Decimal("10"),
        Decimal("16"),
    )
    assert materialized.series.source_artifact_ids == (source_ref.artifact_id,)
    assert len(materialized.certificate.input_authorities) == 1
    assert materialized.certificate.input_authorities[0].artifact_id == source_ref.artifact_id
    derived_manifest = store.get_manifest(materialized.derived_artifact_ref.artifact_id)
    assert tuple(
        (item.role, str(item.artifact_id))
        for item in derived_manifest.inputs
        if item.role.startswith("source:")
    ) == (
        ("source:left", str(source_ref.artifact_id)),
        ("source:right", str(source_ref.artifact_id)),
    )
    assert consumed.series == (Decimal("10"), Decimal("16"))


def test_versioned_family_requires_exact_selection_and_replays_that_version(
    tmp_path: Path,
) -> None:
    v1 = _percent_conversion_family_data()
    v2 = {**_percent_conversion_family_data(), "method_version": "2.0.0"}
    registry = load_transform_family_registry({"families": (v1, v2, _price_rebase_family_data())})
    store, refs, output_basis, _, _ = _case_inputs(
        tmp_path / "cas",
        "percent_of_total_conversion",
    )

    with pytest.raises(DerivationRefusalError) as ambiguous:
        build_derivation_recipe(
            store,
            registry=registry,
            input_refs=refs,
            output_variable_id="test.version.ambiguous",
            output_basis=output_basis,
            family_id="percent_of_total_conversion",
        )
    assert ambiguous.value.reason is DerivationRefusalReason.AMBIGUOUS_CERTIFIED_TRANSFORM

    recipe = build_derivation_recipe(
        store,
        registry=registry,
        input_refs=refs,
        output_variable_id="test.version.explicit",
        output_basis=output_basis,
        family_id="percent_of_total_conversion",
        method_version="2.0.0",
    )
    materialized = materialize_derivation(store, recipe)
    consumed = consume_certified_derivation(
        store,
        certificate_ref=materialized.certificate_artifact_ref,
        consumer_method_id="test.version.consumer@1.0.0",
    )

    assert recipe.method_version == "2.0.0"
    assert materialized.certificate.recipe.family.method_version == "2.0.0"
    assert consumed.series == tuple(point.value for point in materialized.series.points)


def test_recomputed_unregistered_family_is_refused_at_materialization(
    tmp_path: Path,
) -> None:
    store, refs, output_basis, _, _ = _case_inputs(
        tmp_path / "cas",
        "percent_of_total_conversion",
    )
    recipe = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id="test.forged.materialization",
        output_basis=output_basis,
    )
    forged_recipe = _forge_recipe_family(recipe)

    with pytest.raises(DerivationRefusalError) as raised:
        materialize_derivation(store, forged_recipe)

    assert raised.value.code is DerivationRefusalCode.BASIS_MISMATCH
    assert raised.value.reason is DerivationRefusalReason.NO_CERTIFIED_TRANSFORM


def test_recomputed_unregistered_family_is_refused_at_consumption(
    tmp_path: Path,
) -> None:
    store, refs, output_basis, _, _ = _case_inputs(
        tmp_path / "cas",
        "percent_of_total_conversion",
    )
    recipe = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id="test.forged.consumption",
        output_basis=output_basis,
    )
    certificate_ref = _persist_recipe_graph_without_public_intake(
        store,
        _forge_recipe_family(recipe),
    )

    with pytest.raises(DerivationRefusalError) as raised:
        consume_certified_derivation(
            store,
            certificate_ref=certificate_ref,
            consumer_method_id="test.method.forged@1.0.0",
        )

    assert raised.value.code is DerivationRefusalCode.BASIS_MISMATCH
    assert raised.value.reason is DerivationRefusalReason.NO_CERTIFIED_TRANSFORM


def test_unregistered_basis_pair_has_typed_no_transform_refusal(tmp_path: Path) -> None:
    store, refs, _, _, _ = _case_inputs(tmp_path / "cas", "percent_of_total_conversion")
    unseen = _basis("unseen_output", "unknown_unit")

    with pytest.raises(DerivationRefusalError) as raised:
        build_derivation_recipe(
            store,
            registry=_registry(),
            input_refs=refs,
            output_variable_id="test.unseen",
            output_basis=unseen,
        )

    assert raised.value.code is DerivationRefusalCode.BASIS_MISMATCH
    assert raised.value.reason is DerivationRefusalReason.NO_CERTIFIED_TRANSFORM
    assert "no_certified_transform" in str(raised.value)


def test_family_declares_and_certificate_binds_parameter_derivation(tmp_path: Path) -> None:
    store, refs, output_basis, _, _ = _case_inputs(tmp_path / "cas", "price_level_rebase")
    recipe = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id="test.real",
        output_basis=output_basis,
    )

    assert recipe.parameters[0].rule.operator == "lower_median_common_year"
    assert recipe.parameters[0].value == Decimal("2020")
    assert {item.name: item.value for item in recipe.assumptions} == {
        "base_year": "2020",
        "formula": "amount_t * index_base / index_t",
        "source_reference_year": "2010",
        "year_join": "exact; no interpolation",
    }
    assert recipe.output_basis.attribute("base_year") == "2020"


def test_family_rules_materialize_a_different_output_basis_without_caller_logic(
    tmp_path: Path,
) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    refs = {
        "amount": _persist(
            store,
            role="amount",
            basis=CURRENT_MONEY,
            values=((2020, "100"), (2021, "220"), (2022, "360")),
            score="0.8",
        ),
        "index": _persist(
            store,
            role="index",
            basis=PRICE_LEVEL,
            values=((2020, "50"), (2021, "100"), (2022, "120")),
            score="0.7",
        ),
    }
    recipe = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id="test.real.2021",
        family_id="price_level_rebase",
    )
    materialized = materialize_derivation(store, recipe)

    assert recipe.parameters[0].value == Decimal("2021")
    assert recipe.output_basis.attribute("base_year") == "2021"
    assert tuple(point.value for point in materialized.series.points) == (
        Decimal("200"),
        Decimal("220"),
        Decimal("300"),
    )


@pytest.mark.parametrize(
    "family_id",
    ["percent_of_total_conversion", "price_level_rebase"],
)
def test_layer_invariants_are_family_parameterized(
    tmp_path: Path,
    family_id: str,
) -> None:
    store, refs, output_basis, _, authority = _case_inputs(
        tmp_path / family_id,
        family_id,
    )
    recipe = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id=f"test.{family_id}",
        output_basis=output_basis,
    )
    materialized = materialize_derivation(store, recipe)

    derived_payload = materialized.series.model_dump(mode="python")
    derived_payload["observation_class"] = "observed"
    with pytest.raises(ValidationError):
        type(materialized.series).model_validate(derived_payload)

    source_payload = {
        **materialized.series.model_dump(mode="python"),
        "observation_class": "derived",
        "authority": next(iter(_load_authorities(store, refs).values())),
    }
    source_payload.pop("recipe_id")
    source_payload.pop("source_artifact_ids")
    with pytest.raises(ValidationError):
        SourceSeries.model_validate(source_payload)

    certificate_payload = materialized.certificate.model_dump(mode="python")
    certificate_payload["effective_authority"] = min(Decimal("1"), authority + Decimal("0.1"))
    certificate_payload["certificate_id"] = derived_module._identity(
        "derivation-certificate",
        {key: value for key, value in certificate_payload.items() if key != "certificate_id"},
    )
    with pytest.raises(ValidationError, match="weakest"):
        type(materialized.certificate).model_validate(certificate_payload)

    recipe_payload = recipe.model_dump(mode="python")
    recipe_payload["family"]["expression"] = {
        "operator": "constant",
        "constant_value": Decimal("999"),
        "role": None,
        "parameter_name": None,
        "operands": (),
    }
    with pytest.raises(ValidationError, match="identity"):
        type(recipe).model_validate(recipe_payload)

    input_payload = recipe.model_dump(mode="python")
    input_payload["inputs"][0]["artifact"]["artifact_id"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="identity"):
        type(recipe).model_validate(input_payload)


def _load_authorities(
    store: artifacts.FileSystemCAS,
    refs: dict[str, artifacts.ArtifactRef],
) -> dict[str, AuthorityProjection]:
    return {
        role: SourceSeries.model_validate(
            canon.from_canonical_bytes(store.get_bytes(ref.artifact_id))
        ).authority
        for role, ref in refs.items()
    }


def test_recipe_parameter_tamper_is_rejected(tmp_path: Path) -> None:
    store, refs, output_basis, _, _ = _case_inputs(tmp_path / "cas", "price_level_rebase")
    recipe = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id="test.real",
        output_basis=output_basis,
    )
    payload = recipe.model_dump(mode="python")
    payload["parameters"][0]["value"] = Decimal("2019")

    with pytest.raises(ValidationError, match=r"assumptions|output basis|identity"):
        type(recipe).model_validate(payload)


def test_materialization_revalidates_recipe_before_any_cas_write(tmp_path: Path) -> None:
    store, refs, output_basis, _, _ = _case_inputs(
        tmp_path / "cas",
        "percent_of_total_conversion",
    )
    recipe = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id="test.valid.identity",
        output_basis=output_basis,
    )
    forged = recipe.model_copy(update={"output_variable_id": "test.forged.identity"})
    before = tuple(store.iter_artifact_ids())
    refusal: DerivationRefusalError | None = None

    try:
        materialize_derivation(store, forged)
    except DerivationRefusalError as exc:
        refusal = exc

    assert tuple(store.iter_artifact_ids()) == before
    assert refusal is not None
    assert refusal.code is DerivationRefusalCode.INPUT_ARTIFACT_DRIFT


def test_second_materialization_supports_two_verified_consumers(tmp_path: Path) -> None:
    store, refs, output_basis, _, _ = _case_inputs(tmp_path / "cas", "price_level_rebase")
    recipe = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id="test.real",
        output_basis=output_basis,
    )
    materialize_derivation(store, recipe)
    second = materialize_derivation(store, recipe)

    first_consumer = consume_certified_derivation(
        store,
        certificate_ref=second.certificate_artifact_ref,
        consumer_method_id="test.method.first@1.0.0",
    )
    second_consumer = consume_certified_derivation(
        store,
        certificate_ref=second.certificate_artifact_ref,
        consumer_method_id="test.method.second@1.0.0",
    )

    assert first_consumer.derived_artifact_id == second_consumer.derived_artifact_id
    assert first_consumer.certificate_artifact_id == second_consumer.certificate_artifact_id
    assert first_consumer.cache_verified is second_consumer.cache_verified is True
    assert first_consumer.observation_class == "derived"


@pytest.mark.parametrize("mutation", ["bytes", "kind", "schema", "producer", "inputs"])
def test_cache_hit_reopens_bytes_and_manifest_contract(
    tmp_path: Path,
    mutation: str,
) -> None:
    store, refs, output_basis, _, _ = _case_inputs(tmp_path / mutation, "price_level_rebase")
    recipe = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id="test.real",
        output_basis=output_basis,
    )
    first = materialize_derivation(store, recipe)
    blob_path, manifest_path = store.get_paths(first.derived_artifact_ref.artifact_id)
    if mutation == "bytes":
        blob_path.write_bytes(b"{}")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if mutation == "kind":
            manifest["kind"] = "forged.kind"
        elif mutation == "schema":
            manifest["schema"]["version"] = "forged"
        elif mutation == "producer":
            manifest["producer"]["version"] = "forged"
        else:
            manifest["inputs"] = []
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DerivationRefusalError) as raised:
        materialize_derivation(store, recipe)
    assert raised.value.code is DerivationRefusalCode.CACHE_ARTIFACT_DRIFT


def test_source_manifest_and_authority_graph_are_reopened(tmp_path: Path) -> None:
    store, refs, output_basis, _, _ = _case_inputs(tmp_path / "cas", "price_level_rebase")
    recipe = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id="test.real",
        output_basis=output_basis,
    )
    authority_edge = next(
        item
        for item in store.get_manifest(refs["amount"].artifact_id).inputs
        if item.role == "authority_evidence"
    )
    authority_blob, _ = store.get_paths(authority_edge.artifact_id)
    authority_blob.write_bytes(b"{}")

    with pytest.raises(DerivationRefusalError) as raised:
        materialize_derivation(store, recipe)
    assert raised.value.code is DerivationRefusalCode.INPUT_ARTIFACT_DRIFT


@pytest.mark.parametrize("mutation", ["schema", "producer", "inputs"])
def test_recipe_construction_rejects_forged_source_manifest_contract(
    tmp_path: Path,
    mutation: str,
) -> None:
    store, refs, _, _, _ = _case_inputs(
        tmp_path / mutation,
        "percent_of_total_conversion",
    )
    forged_source = SourceSeries(
        variable_id=f"test.forged.{mutation}",
        basis=PERCENT_SHARE,
        points=(SeriesPoint(year=2020, value=Decimal("5")),),
        authority=_authority(store, label=f"forged-{mutation}", score="0.8"),
        observation_class="observed",
    )
    schema = artifacts.SchemaInfo(
        name="polisyos.runtime.derivation-source-series",
        version="2.0.0",
    )
    producer = _source_producer()
    inputs = derived_module._authority_input_refs(forged_source.authority)
    if mutation == "schema":
        schema = artifacts.SchemaInfo(name="forged.source", version="9.9.9")
    elif mutation == "producer":
        producer = artifacts.ProducerInfo(component="forged.source", version="9.9.9")
    else:
        inputs = []
    forged_ref = store.put_bytes(
        canon.to_canonical_bytes(forged_source, derived_module._CANON_SPEC),
        artifacts.PutOptions(
            kind=derived_module.SOURCE_SERIES_KIND,
            media_type="application/json",
            schema=schema,
            producer=producer,
            inputs=inputs,
            canon=artifacts.CanonInfo.from_spec(derived_module._CANON_SPEC),
        ),
    )

    with pytest.raises(DerivationRefusalError) as raised:
        build_derivation_recipe(
            store,
            registry=_registry(),
            input_refs={"share": forged_ref, "total": refs["total"]},
            output_variable_id=f"test.forged.{mutation}.output",
            output_basis=CURRENT_USD,
        )

    assert raised.value.code is DerivationRefusalCode.INPUT_ARTIFACT_DRIFT


def test_source_intake_rejects_an_unregistered_unit(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    source = SourceSeries(
        variable_id="test.unknown.unit",
        basis=_basis("novel_quantity", "unknown_unit"),
        points=(SeriesPoint(year=2020, value=Decimal("1")),),
        authority=_authority(store, label="unknown-unit", score="0.8"),
        observation_class="observed",
    )
    ref = store.put_bytes(
        canon.to_canonical_bytes(source, derived_module._CANON_SPEC),
        artifacts.PutOptions(
            kind=derived_module.SOURCE_SERIES_KIND,
            media_type="application/json",
            schema=derived_module._SOURCE_SERIES_SCHEMA,
            producer=_source_producer(),
            inputs=derived_module._authority_input_refs(source.authority),
            canon=artifacts.CanonInfo.from_spec(derived_module._CANON_SPEC),
        ),
    )
    projection = derived_module._manifest_projection(store, ref.artifact_id)

    with pytest.raises(DerivationRefusalError) as raised:
        derived_module._load_source(
            store,
            projection,
            refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
        )

    assert raised.value.code is DerivationRefusalCode.BASIS_MISMATCH
    assert raised.value.reason is DerivationRefusalReason.NO_CERTIFIED_TRANSFORM


def test_exact_year_and_declared_numeric_constraints_fail_closed(tmp_path: Path) -> None:
    missing_store = artifacts.FileSystemCAS(tmp_path / "missing")
    missing_refs = {
        "share": _persist(
            missing_store,
            role="share",
            basis=PERCENT_SHARE,
            values=((2019, "5"), (2020, "6")),
            score="0.8",
        ),
        "total": _persist(
            missing_store,
            role="total",
            basis=CURRENT_USD,
            values=((2019, "100"),),
            score="0.7",
        ),
    }
    missing_recipe = build_derivation_recipe(
        missing_store,
        registry=_registry(),
        input_refs=missing_refs,
        output_variable_id="test.missing",
        output_basis=CURRENT_USD,
    )
    with pytest.raises(DerivationRefusalError) as missing:
        materialize_derivation(missing_store, missing_recipe)
    assert missing.value.code is DerivationRefusalCode.EXACT_YEAR_MISSING

    constraint_store = artifacts.FileSystemCAS(tmp_path / "constraint")
    constraint_refs = {
        "amount": _persist(
            constraint_store,
            role="amount",
            basis=CURRENT_MONEY,
            values=((2020, "100"),),
            score="0.8",
        ),
        "index": _persist(
            constraint_store,
            role="index",
            basis=PRICE_LEVEL,
            values=((2020, "0"),),
            score="0.7",
        ),
    }
    constraint_recipe = build_derivation_recipe(
        constraint_store,
        registry=_registry(),
        input_refs=constraint_refs,
        output_variable_id="test.constraint",
        output_basis=CONSTANT_MONEY,
    )
    with pytest.raises(DerivationRefusalError) as constrained:
        materialize_derivation(constraint_store, constraint_recipe)
    assert constrained.value.code is DerivationRefusalCode.INPUT_VALUE_CONSTRAINT


def test_contract_models_reject_noncanonical_and_nonfinite_data() -> None:
    with pytest.raises(ValidationError, match="sorted"):
        BasisSignature(
            quantity_kind="test",
            unit="test",
            attributes=(
                BasisAttribute(name="z", value="1"),
                BasisAttribute(name="a", value="2"),
            ),
        )
    with pytest.raises(ValidationError, match="finite"):
        SeriesPoint(year=2020, value=Decimal("NaN"))
    with pytest.raises(ValidationError, match="two operands"):
        ArithmeticExpression(
            operator="multiply",
            operands=(ArithmeticExpression(operator="constant", constant_value=Decimal("1")),),
        )


def test_registry_rejects_duplicate_and_ambiguous_family_definitions() -> None:
    family = TransformFamily.model_validate(_percent_conversion_family_data())
    with pytest.raises(ValidationError, match="unique"):
        TransformFamilyRegistry(families=(family, family))

    duplicate = family.model_copy(update={"family_id": "alternate_family"})
    registry = TransformFamilyRegistry(families=(duplicate, family))
    with pytest.raises(DerivationRefusalError) as raised:
        registry.resolve(
            input_bases={"share": PERCENT_SHARE, "total": CURRENT_USD},
            output_basis=CURRENT_USD,
        )
    assert raised.value.reason is DerivationRefusalReason.AMBIGUOUS_CERTIFIED_TRANSFORM


def test_registry_rejects_noncanonical_family_order_and_keeps_stable_identity(
    tmp_path: Path,
) -> None:
    canonical_payload = {
        "families": (
            _percent_conversion_family_data(),
            _price_rebase_family_data(),
        )
    }
    canonical = load_transform_family_registry(canonical_payload)
    with pytest.raises(ValidationError, match="sorted"):
        load_transform_family_registry({"families": tuple(reversed(canonical_payload["families"]))})

    first_ref = persist_transform_family_registry(
        artifacts.FileSystemCAS(tmp_path / "first"),
        canonical,
    )
    second_ref = persist_transform_family_registry(
        artifacts.FileSystemCAS(tmp_path / "second"),
        load_transform_family_registry(canonical_payload),
    )

    assert second_ref.artifact_id == first_ref.artifact_id


@pytest.mark.parametrize("construction", ["model_copy", "model_construct"])
def test_registry_persistence_revalidates_before_any_cas_write(
    tmp_path: Path,
    construction: str,
) -> None:
    registry = _registry()
    reversed_families = tuple(reversed(registry.families))
    if construction == "model_copy":
        forged = registry.model_copy(update={"families": reversed_families})
    else:
        forged = TransformFamilyRegistry.model_construct(families=reversed_families)
    store = artifacts.FileSystemCAS(tmp_path / construction)
    before = tuple(store.iter_artifact_ids())
    refusal: DerivationRefusalError | None = None

    try:
        persist_transform_family_registry(store, forged)
    except DerivationRefusalError as exc:
        refusal = exc

    assert tuple(store.iter_artifact_ids()) == before
    assert refusal is not None
    assert refusal.code is DerivationRefusalCode.INPUT_ARTIFACT_DRIFT


def test_bad_family_parameter_output_binding_is_typed_refused(tmp_path: Path) -> None:
    bad_output = _basis(
        "monetary_flow",
        "UAH_constant",
        base_year="2019",
        currency="UAH",
        price_basis="constant",
    )
    store, refs, _, _, _ = _case_inputs(tmp_path / "cas", "price_level_rebase")

    with pytest.raises(DerivationRefusalError) as raised:
        build_derivation_recipe(
            store,
            registry=_registry(),
            input_refs=refs,
            output_variable_id="test.bad_parameter",
            output_basis=bad_output,
        )

    assert raised.value.code is DerivationRefusalCode.BASIS_MISMATCH
    assert raised.value.reason is DerivationRefusalReason.NO_CERTIFIED_TRANSFORM


def test_test_family_definitions_are_plain_owner_data() -> None:
    payload: dict[str, Any] = _percent_conversion_family_data()
    family = load_transform_family_registry({"families": (payload,)}).families[0]
    assert family.family_id == payload["family_id"]
    assert family.expression.operator == "divide"


def test_registry_loader_typed_refuses_an_unregistered_unit() -> None:
    family = _percent_conversion_family_data()
    family["output_basis"] = _basis("novel_output", "unknown_unit")

    with pytest.raises(DerivationRefusalError) as raised:
        load_transform_family_registry({"families": (family,)})

    assert raised.value.code is DerivationRefusalCode.BASIS_MISMATCH
    assert raised.value.reason is DerivationRefusalReason.NO_CERTIFIED_TRANSFORM


def test_registry_loads_an_unseen_family_from_toml(tmp_path: Path) -> None:
    path = tmp_path / "families.toml"
    path.write_text(
        """
[[families]]
family_id = "toml_identity_family"
method_id = "arithmetic.identity"
method_version = "1.0.0"
year_domain_role = "source"
parameter_rules = []
output_parameter_bindings = []

[families.output_basis]
quantity_kind = "toml_output"
unit = "usd"
attributes = []

[families.expression]
operator = "current_value"
role = "source"

[[families.input_specs]]
role = "source"
value_constraints = []

[families.input_specs.basis]
quantity_kind = "toml_input"
unit = "ratio"
attributes = []

[[families.assumption_rules]]
name = "formula"
literal_value = "identity"
""".strip(),
        encoding="utf-8",
    )

    registry = load_transform_family_registry(path)

    assert registry.families[0].family_id == "toml_identity_family"
    assert registry.families[0].expression.operator == "current_value"


def test_v1_direct_exports_remain_a_typed_fail_closed_boundary() -> None:
    legacy_exports = {
        "ECONOMIC_SERIES_KIND",
        "PRICE_INDEX_SERIES_KIND",
        "EconomicBasis",
        "EconomicSeries",
        "PriceIndexBasis",
        "PriceIndexSeries",
        "DerivedEconomicSeries",
        "build_cpi_derivation_recipe",
        "materialize_cpi_real_terms",
        "persist_economic_series",
        "persist_price_index_series",
    }

    assert legacy_exports.issubset(set(derived_module.__all__))
    with pytest.raises(DerivationRefusalError) as model_refusal:
        derived_module.EconomicSeries.model_validate({})
    with pytest.raises(DerivationRefusalError) as builder_refusal:
        derived_module.build_cpi_derivation_recipe(None)
    with pytest.raises(DerivationRefusalError) as recipe_refusal:
        derived_module.DerivationRecipe.model_validate(
            {"schema_version": "polisyos.runtime.derived_observations.v1"}
        )
    with pytest.raises(DerivationRefusalError) as certificate_refusal:
        derived_module.DerivationCertificate.model_validate(
            {"schema_version": "polisyos.runtime.derived_observations.v1"}
        )

    assert model_refusal.value.code.value == "legacy_schema_unsupported"
    assert builder_refusal.value.code.value == "legacy_schema_unsupported"
    assert recipe_refusal.value.code.value == "legacy_schema_unsupported"
    assert certificate_refusal.value.code.value == "legacy_schema_unsupported"


def test_persisted_v1_certificate_is_recognized_and_typed_refused(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    certificate_ref = store.put_bytes(
        canon.to_canonical_bytes(
            {"schema_version": "polisyos.runtime.derived_observations.v1"},
            derived_module._CANON_SPEC,
        ),
        artifacts.PutOptions(
            kind=derived_module.DERIVATION_CERTIFICATE_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="polisyos.runtime.derivation-certificate",
                version="1.0.0",
            ),
            producer=artifacts.ProducerInfo(
                component="polisyos.runtime.quality.derived_observations",
                version="1.0.0",
            ),
        ),
    )

    with pytest.raises(DerivationRefusalError) as raised:
        consume_certified_derivation(
            store,
            certificate_ref=certificate_ref,
            consumer_method_id="test.v1.consumer@1.0.0",
        )

    assert raised.value.code.value == "legacy_schema_unsupported"


def _epoch_digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _epoch_manifest(
    *,
    label: str,
    predecessors: tuple[str, ...],
) -> semantic_epoch_runtime.SemanticEpochManifest:
    scope = semantic_epoch_runtime.build_epoch_scope_identity(
        schema_profile="polisyos.epoch.recompute-test-scope.v1",
        identity_bytes=b"derived-observations-recompute",
    )
    values: dict[str, object] = {
        "schema_version": "polisyos.epoch.semantic-manifest.v1",
        "scope_identity": scope.model_dump(mode="json"),
        "authority_purpose": "decision_validity_epoch_transition",
        "valid_effect_coordinate_ref": _epoch_digest("valid-effect"),
        "visibility_knowledge_cutoff_ref": _epoch_digest("knowledge-cutoff"),
        "purpose_admission_cutoff_ref": _epoch_digest("purpose-cutoff"),
        "requested_query_context_ref": _epoch_digest(f"manifest-query:{label}"),
        "boundary_registry_content_hash": _epoch_digest("boundary-registry"),
        "facet_registry_content_hash": _epoch_digest("facet-registry"),
        "boundary_denominator_hash": _epoch_digest(f"boundary:{label}"),
        "facet_denominator_hash": _epoch_digest("facet-denominator"),
        "boundary_semantic_hashes": [_epoch_digest(f"boundary-semantic:{label}")],
        "facet_semantic_hashes": [_epoch_digest("facet-semantic")],
        "predecessor_refs": list(predecessors),
    }
    manifest_hash = semantic_epoch_runtime._model_hash(
        semantic_epoch_runtime._MANIFEST_PREFIX,
        values,
    )
    return semantic_epoch_runtime.SemanticEpochManifest(
        **values,
        manifest_content_hash=manifest_hash,
        epoch_ref=semantic_epoch_runtime._sha256(
            semantic_epoch_runtime._EPOCH_PREFIX,
            manifest_hash.encode(),
        ),
    )


@dataclass(frozen=True)
class _EpochRecomputeFixture:
    store: artifacts.FileSystemCAS
    transition_ref: artifacts.ArtifactRef
    transition: epoch_cascade.EpochValidityTransitionArtifact
    source_ref: artifacts.ArtifactRef
    target_ref: artifacts.ArtifactRef
    certificate_ref: artifacts.ArtifactRef
    recipe_ref: artifacts.ArtifactRef
    derived_ref: artifacts.ArtifactRef
    relation: str
    disposition: str
    query_ref: str
    purpose: str


def _epoch_recompute_fixture(
    tmp_path: Path,
    *,
    output_label: str = "primary",
) -> _EpochRecomputeFixture:
    store, refs, output_basis, _, _ = _case_inputs(
        tmp_path / "cas",
        "price_level_rebase",
    )
    recipe = build_derivation_recipe(
        store,
        registry=_registry(),
        input_refs=refs,
        output_variable_id=f"test.epoch.recomputed.{output_label}",
        output_basis=output_basis,
    )
    materialized = materialize_derivation(store, recipe)
    recipe_ref = derived_module.persist_derivation_recipe_artifact(store, recipe)
    previous = _epoch_manifest(label="previous", predecessors=())
    current = _epoch_manifest(label="current", predecessors=(previous.epoch_ref,))
    purpose = "decision_validity_epoch_transition"
    query_ref = _epoch_digest("recompute-query")
    source_ref = refs["amount"]
    target_ref = materialized.certificate_artifact_ref
    relation = "derived_output_inherits_epoch"
    recipe_binding = epoch_cascade.DerivationRecipeBinding(
        recipe_ref=recipe_ref,
        recipe_content_hash=str(recipe_ref.artifact_id),
        recipe_schema_profile_ref=_epoch_digest("derivation-recipe-profile"),
        input_roles=tuple(sorted(refs)),
    )
    certificate_binding = epoch_cascade.bind_certificate_to_epoch(
        certificate_ref=materialized.certificate_artifact_ref,
        certificate_content_hash=str(materialized.certificate_artifact_ref.artifact_id),
        epoch=previous,
        input_certificate_refs=tuple(refs[key] for key in sorted(refs)),
        recipe=recipe_binding,
        canonical_producer_ref="polisyos.runtime.quality.derived_observations@2.0.0",
        authority_purpose=purpose,
        native_coordinate_refs=(),
        rule_schema_profile_refs=(_epoch_digest("derivation-rule-profile"),),
    )
    edges = (
        epoch_cascade.EpochDependencyEdge(
            source_ref=source_ref,
            target_ref=target_ref,
            relation=relation,
            authority_purpose=purpose,
        ),
    )
    graph = epoch_cascade.EpochDependencyGraph(
        edges=edges,
        denominator_ref=epoch_cascade._semantic_hash(
            "polisyos.epoch.dependency-graph.v1",
            {"edges": edges},
        ),
    )
    vector = epoch_cascade.resolve_owner_target_dispositions(
        advisory_events=(),
        owner_dispositions=(),
        dependency_graph=graph,
    )
    transition = epoch_cascade.build_epoch_validity_transition(
        previous_epoch=previous,
        current_epoch=current,
        certificates=(certificate_binding,),
        dependency_graph=graph,
        target_vector=vector,
        dependency_denominator_ref=graph.denominator_ref,
        adjudication_denominator_ref=_epoch_digest("adjudication-denominator"),
        requested_query_context_ref=query_ref,
        authority_purpose=purpose,
    )
    transition_ref = store.put_bytes(
        epoch_cascade._canonical_bytes(transition),
        artifacts.ArtifactWriteOptions(
            kind="polisyos.epoch.validity_transition",
            media_type="application/vnd.polisyos.chronology+json",
        ),
    )
    return _EpochRecomputeFixture(
        store=store,
        transition_ref=transition_ref,
        transition=transition,
        source_ref=source_ref,
        target_ref=target_ref,
        certificate_ref=materialized.certificate_artifact_ref,
        recipe_ref=recipe_ref,
        derived_ref=materialized.derived_artifact_ref,
        relation=relation,
        disposition="unchanged",
        query_ref=query_ref,
        purpose=purpose,
    )


def _produce_epoch_recompute(
    fixture: _EpochRecomputeFixture,
    **changes: object,
):
    values: dict[str, object] = {
        "transition_ref": fixture.transition_ref,
        "expected_previous_epoch_ref": fixture.transition.previous_epoch_ref,
        "expected_current_epoch_ref": fixture.transition.current_epoch_ref,
        "requested_query_context_ref": fixture.query_ref,
        "authority_purpose": fixture.purpose,
        "source_ref": fixture.source_ref,
        "target_ref": fixture.target_ref,
        "relation": fixture.relation,
        "expected_target_disposition": fixture.disposition,
        "certificate_ref": fixture.certificate_ref,
    }
    values.update(changes)
    return derived_module.produce_epoch_inheritance_recompute_receipt(
        fixture.store,
        **values,
    )


def _read_epoch_recompute(
    fixture: _EpochRecomputeFixture,
    receipt_ref: artifacts.ArtifactRef,
    **changes: object,
):
    values: dict[str, object] = {
        "receipt_ref": receipt_ref,
        "expected_previous_epoch_ref": fixture.transition.previous_epoch_ref,
        "expected_current_epoch_ref": fixture.transition.current_epoch_ref,
        "requested_query_context_ref": fixture.query_ref,
        "authority_purpose": fixture.purpose,
        "source_ref": fixture.source_ref,
        "target_ref": fixture.target_ref,
        "relation": fixture.relation,
        "expected_target_disposition": fixture.disposition,
        "certificate_ref": fixture.certificate_ref,
    }
    values.update(changes)
    return derived_module.read_epoch_inheritance_recompute_receipt(
        fixture.store,
        **values,
    )


def test_epoch_inheritance_recompute_receipt_round_trips_exact_owner_graph(
    tmp_path: Path,
) -> None:
    fixture = _epoch_recompute_fixture(tmp_path)

    persisted = _produce_epoch_recompute(fixture)
    reread = _read_epoch_recompute(fixture, persisted.receipt_artifact_ref)
    raw = fixture.store.get_bytes(persisted.receipt_artifact_ref.artifact_id)
    manifest = fixture.store.get_manifest(persisted.receipt_artifact_ref.artifact_id)
    payload = derived_module._canonical_payload(raw)

    assert reread == persisted
    assert persisted.receipt_content_hash == str(persisted.receipt_artifact_ref.artifact_id)
    assert payload["state"] == "completed"
    assert payload["predicate_class"] == "recomputed"
    assert payload["derived_artifact_ref"] == fixture.derived_ref.model_dump(mode="json")
    assert "series" not in payload
    assert tuple((row.role, str(row.artifact_id)) for row in manifest.inputs) == (
        ("derivation_certificate", str(fixture.certificate_ref.artifact_id)),
        ("derivation_recipe", str(fixture.recipe_ref.artifact_id)),
        ("derived_series", str(fixture.derived_ref.artifact_id)),
        ("epoch_transition", str(fixture.transition_ref.artifact_id)),
        ("graph_edge_source", str(fixture.source_ref.artifact_id)),
        ("graph_edge_target", str(fixture.target_ref.artifact_id)),
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("expected_current_epoch_ref", _epoch_digest("authentic-old-current")),
        ("requested_query_context_ref", _epoch_digest("substituted-query")),
        ("authority_purpose", "substituted_purpose"),
        ("relation", "sibling_relation"),
        ("expected_target_disposition", "reissue"),
    ],
)
def test_epoch_inheritance_recompute_rejects_coordinate_or_edge_substitution(
    tmp_path: Path,
    field: str,
    replacement: str,
) -> None:
    fixture = _epoch_recompute_fixture(tmp_path)

    with pytest.raises(DerivationRefusalError) as raised:
        _produce_epoch_recompute(fixture, **{field: replacement})

    assert raised.value.code is DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT


def test_epoch_inheritance_recompute_rejects_authentic_certificate_substitution(
    tmp_path: Path,
) -> None:
    fixture = _epoch_recompute_fixture(tmp_path / "first")
    other = _epoch_recompute_fixture(tmp_path / "other", output_label="substituted")

    with pytest.raises(DerivationRefusalError) as raised:
        _produce_epoch_recompute(fixture, certificate_ref=other.certificate_ref)

    assert raised.value.code is DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT


@pytest.mark.parametrize("artifact", ["receipt", "transition", "certificate", "derived"])
def test_epoch_inheritance_recompute_reader_rejects_owner_artifact_drift(
    tmp_path: Path,
    artifact: str,
) -> None:
    fixture = _epoch_recompute_fixture(tmp_path)
    persisted = _produce_epoch_recompute(fixture)
    ref = {
        "receipt": persisted.receipt_artifact_ref,
        "transition": fixture.transition_ref,
        "certificate": fixture.certificate_ref,
        "derived": fixture.derived_ref,
    }[artifact]
    blob_path, _ = fixture.store.get_paths(ref.artifact_id)
    blob_path.write_bytes(blob_path.read_bytes() + b"corrupt")

    with pytest.raises(DerivationRefusalError):
        _read_epoch_recompute(fixture, persisted.receipt_artifact_ref)


def test_epoch_inheritance_recompute_reader_rejects_receipt_manifest_input_drift(
    tmp_path: Path,
) -> None:
    fixture = _epoch_recompute_fixture(tmp_path)
    persisted = _produce_epoch_recompute(fixture)
    _, manifest_path = fixture.store.get_paths(persisted.receipt_artifact_ref.artifact_id)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["inputs"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DerivationRefusalError) as raised:
        _read_epoch_recompute(fixture, persisted.receipt_artifact_ref)

    assert raised.value.code is DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT
