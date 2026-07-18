"""Semantic tests for certified, content-addressed economic derivations."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core import artifacts
from polisyos.foundry.methods.catalog.forecasting.univariate import (
    ExponentialSmoothingEstimator,
    ThetaMethodEstimator,
)
from polisyos.ir.kernel import DimensionlessUnit, MoneyUnit
from polisyos.runtime.quality.derived_observations import (
    AuthorityProjection,
    DerivationRefusalCode,
    DerivationRefusalError,
    EconomicBasis,
    EconomicSeries,
    PriceIndexBasis,
    PriceIndexSeries,
    SeriesPoint,
    build_cpi_derivation_recipe,
    consume_certified_derivation,
    materialize_cpi_real_terms,
    persist_economic_series,
    persist_price_index_series,
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
        component="polisyos.tests.owner_validated_series",
        version="1.0.0",
    )


def _nominal_basis() -> EconomicBasis:
    return EconomicBasis(
        unit=MoneyUnit(
            kind="money",
            currency="UAH",
            nominal_year=None,
            price_base=None,
        ),
        price_basis="nominal",
        base_year=None,
        deflator_ref=None,
        deflator_version=None,
        per_capita=False,
        seasonal_adjustment="not_seasonally_adjusted",
    )


def _price_index_basis() -> PriceIndexBasis:
    return PriceIndexBasis(
        unit=DimensionlessUnit(kind="dimensionless", label="index"),
        index_id="consumer_price_index",
        index_version="worldbank.wdi.FP.CPI.TOTL@2026-07-18",
        reference_base_year=2010,
        seasonal_adjustment="not_seasonally_adjusted",
    )


def _source_artifacts(
    root: Path,
) -> tuple[artifacts.FileSystemCAS, artifacts.ArtifactRef, artifacts.ArtifactRef]:
    store = artifacts.FileSystemCAS(root)
    nominal = EconomicSeries(
        variable_id="gdp_nominal_lcu",
        basis=_nominal_basis(),
        points=(
            SeriesPoint(year=2019, value=Decimal("100")),
            SeriesPoint(year=2020, value=Decimal("220")),
            SeriesPoint(year=2021, value=Decimal("360")),
        ),
        authority=_authority(store, label="nominal", score="0.82"),
        observation_class="observed",
    )
    deflator = PriceIndexSeries(
        variable_id="consumer_price_index",
        basis=_price_index_basis(),
        points=(
            SeriesPoint(year=2019, value=Decimal("50")),
            SeriesPoint(year=2020, value=Decimal("100")),
            SeriesPoint(year=2021, value=Decimal("120")),
        ),
        authority=_authority(store, label="deflator", score="0.71"),
        observation_class="observed",
    )
    nominal_ref = persist_economic_series(store, nominal, producer=_source_producer())
    deflator_ref = persist_price_index_series(store, deflator, producer=_source_producer())
    return store, nominal_ref, deflator_ref


def _real_basis(
    deflator_ref: artifacts.ArtifactRef,
    *,
    base_year: int = 2020,
    currency: str = "UAH",
) -> EconomicBasis:
    return EconomicBasis(
        unit=MoneyUnit(
            kind="money",
            currency=currency,
            nominal_year=base_year,
            price_base="consumer_price_index",
        ),
        price_basis="real",
        base_year=base_year,
        deflator_ref=deflator_ref.artifact_id,
        deflator_version="worldbank.wdi.FP.CPI.TOTL@2026-07-18",
        per_capita=False,
        seasonal_adjustment="not_seasonally_adjusted",
    )


def _assumptions(*, base_year: int = 2020) -> tuple[str, ...]:
    return (
        f"base_year={base_year}",
        "deflator_version=worldbank.wdi.FP.CPI.TOTL@2026-07-18",
        "exact-year joins; no interpolation",
        "real_t = nominal_t * CPI_base / CPI_t",
    )


def test_economic_basis_has_no_silent_defaults() -> None:
    with pytest.raises(ValidationError):
        EconomicBasis.model_validate(
            {
                "unit": MoneyUnit(
                    kind="money",
                    currency="UAH",
                    nominal_year=None,
                    price_base=None,
                ),
                "price_basis": "nominal",
            }
        )

    basis = EconomicBasis(
        unit=MoneyUnit(
            kind="money",
            currency="UAH",
            nominal_year=None,
            price_base=None,
        ),
        price_basis="nominal",
        base_year=None,
        deflator_ref=None,
        deflator_version=None,
        per_capita=False,
        seasonal_adjustment="not_seasonally_adjusted",
    )

    assert basis.price_basis == "nominal"


def test_cpi_recipe_materializes_exact_real_terms_and_caps_authority(tmp_path: Path) -> None:
    store, nominal_ref, deflator_ref = _source_artifacts(tmp_path / "cas")
    recipe = build_cpi_derivation_recipe(
        store,
        nominal_ref=nominal_ref,
        deflator_ref=deflator_ref,
        output_variable_id="gdp_real_lcu_2020",
        output_basis=_real_basis(deflator_ref),
        assumptions=_assumptions(),
    )

    materialized = materialize_cpi_real_terms(store, recipe)

    assert materialized.cache_hit is False
    assert tuple(point.value for point in materialized.series.points) == (
        Decimal("200"),
        Decimal("220"),
        Decimal("300"),
    )
    assert materialized.series.observation_class == "derived"
    assert materialized.certificate.effective_authority == Decimal("0.71")
    assert materialized.certificate.observation_class == "derived"
    assert "observed_series" in materialized.certificate.may_not_use_for


def test_basis_mismatch_is_a_typed_refusal(tmp_path: Path) -> None:
    store, nominal_ref, deflator_ref = _source_artifacts(tmp_path / "cas")

    with pytest.raises(DerivationRefusalError) as raised:
        build_cpi_derivation_recipe(
            store,
            nominal_ref=nominal_ref,
            deflator_ref=deflator_ref,
            output_variable_id="gdp_real_usd_2020",
            output_basis=_real_basis(deflator_ref, currency="USD"),
            assumptions=_assumptions(),
        )

    assert raised.value.code is DerivationRefusalCode.BASIS_MISMATCH


def test_materialization_requires_base_year_and_every_exact_year(tmp_path: Path) -> None:
    store, nominal_ref, deflator_ref = _source_artifacts(tmp_path / "base-year")
    base_missing_recipe = build_cpi_derivation_recipe(
        store,
        nominal_ref=nominal_ref,
        deflator_ref=deflator_ref,
        output_variable_id="gdp_real_lcu_2018",
        output_basis=_real_basis(deflator_ref, base_year=2018),
        assumptions=_assumptions(base_year=2018),
    )
    with pytest.raises(DerivationRefusalError) as base_missing:
        materialize_cpi_real_terms(store, base_missing_recipe)
    assert base_missing.value.code is DerivationRefusalCode.BASE_YEAR_MISSING

    exact_store = artifacts.FileSystemCAS(tmp_path / "exact-year")
    nominal = EconomicSeries(
        variable_id="gdp_nominal_lcu",
        basis=_nominal_basis(),
        points=(
            SeriesPoint(year=2019, value=Decimal("100")),
            SeriesPoint(year=2020, value=Decimal("220")),
        ),
        authority=_authority(exact_store, label="nominal", score="0.8"),
        observation_class="observed",
    )
    deflator = PriceIndexSeries(
        variable_id="consumer_price_index",
        basis=_price_index_basis(),
        points=(SeriesPoint(year=2020, value=Decimal("100")),),
        authority=_authority(exact_store, label="deflator", score="0.7"),
        observation_class="observed",
    )
    nominal_exact_ref = persist_economic_series(
        exact_store,
        nominal,
        producer=_source_producer(),
    )
    deflator_exact_ref = persist_price_index_series(
        exact_store,
        deflator,
        producer=_source_producer(),
    )
    exact_recipe = build_cpi_derivation_recipe(
        exact_store,
        nominal_ref=nominal_exact_ref,
        deflator_ref=deflator_exact_ref,
        output_variable_id="gdp_real_lcu_2020",
        output_basis=_real_basis(deflator_exact_ref),
        assumptions=_assumptions(),
    )
    with pytest.raises(DerivationRefusalError) as exact_missing:
        materialize_cpi_real_terms(exact_store, exact_recipe)
    assert exact_missing.value.code is DerivationRefusalCode.EXACT_YEAR_MISSING


def test_series_contract_rejects_duplicate_nonfinite_and_nonpositive_values(
    tmp_path: Path,
) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    authority = _authority(store, label="source", score="0.7")
    with pytest.raises(ValidationError, match="unique"):
        EconomicSeries(
            variable_id="gdp_nominal_lcu",
            basis=_nominal_basis(),
            points=(
                SeriesPoint(year=2020, value=Decimal("1")),
                SeriesPoint(year=2020, value=Decimal("2")),
            ),
            authority=authority,
            observation_class="observed",
        )
    with pytest.raises(ValidationError, match="finite"):
        SeriesPoint(year=2020, value=Decimal("NaN"))
    with pytest.raises(ValidationError, match="positive"):
        PriceIndexSeries(
            variable_id="consumer_price_index",
            basis=_price_index_basis(),
            points=(SeriesPoint(year=2020, value=Decimal("0")),),
            authority=authority,
            observation_class="observed",
        )


def test_second_materialization_verifies_one_cache_hit_and_two_consumers(
    tmp_path: Path,
) -> None:
    store, nominal_ref, deflator_ref = _source_artifacts(tmp_path / "cas")
    recipe = build_cpi_derivation_recipe(
        store,
        nominal_ref=nominal_ref,
        deflator_ref=deflator_ref,
        output_variable_id="gdp_real_lcu_2020",
        output_basis=_real_basis(deflator_ref),
        assumptions=_assumptions(),
    )
    first = materialize_cpi_real_terms(store, recipe)
    second = materialize_cpi_real_terms(store, recipe)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.derived_artifact_ref == first.derived_artifact_ref
    assert second.certificate_artifact_ref == first.certificate_artifact_ref

    ets = consume_certified_derivation(
        store,
        certificate_ref=second.certificate_artifact_ref,
        consumer_method_id="forecasting.univariate.exponential_smoothing@1.0.0",
    )
    theta = consume_certified_derivation(
        store,
        certificate_ref=second.certificate_artifact_ref,
        consumer_method_id="forecasting.univariate.theta@1.0.0",
    )

    assert ets.derived_artifact_id == theta.derived_artifact_id
    assert ets.certificate_artifact_id == theta.certificate_artifact_id
    assert ets.cache_verified is theta.cache_verified is True
    ets_result = ExponentialSmoothingEstimator.pure_step(
        {"series": [float(value) for value in ets.series]},
        {"horizon": 1},
    )
    theta_result = ThetaMethodEstimator.pure_step(
        {"series": [float(value) for value in theta.series]},
        {"horizon": 1},
    )
    assert len(ets_result["result"]["forecast"]) == 1
    assert len(theta_result["result"]["forecast"]) == 1


@pytest.mark.parametrize("mutation", ["bytes", "kind", "schema", "producer", "inputs"])
def test_cache_hit_reopens_bytes_and_full_manifest_contract(
    tmp_path: Path,
    mutation: str,
) -> None:
    store, nominal_ref, deflator_ref = _source_artifacts(tmp_path / mutation)
    recipe = build_cpi_derivation_recipe(
        store,
        nominal_ref=nominal_ref,
        deflator_ref=deflator_ref,
        output_variable_id="gdp_real_lcu_2020",
        output_basis=_real_basis(deflator_ref),
        assumptions=_assumptions(),
    )
    first = materialize_cpi_real_terms(store, recipe)
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
        materialize_cpi_real_terms(store, recipe)
    assert raised.value.code is DerivationRefusalCode.CACHE_ARTIFACT_DRIFT


def test_recipe_certificate_and_derived_class_cannot_be_pinned(tmp_path: Path) -> None:
    store, nominal_ref, deflator_ref = _source_artifacts(tmp_path / "cas")
    recipe = build_cpi_derivation_recipe(
        store,
        nominal_ref=nominal_ref,
        deflator_ref=deflator_ref,
        output_variable_id="gdp_real_lcu_2020",
        output_basis=_real_basis(deflator_ref),
        assumptions=_assumptions(),
    )
    materialized = materialize_cpi_real_terms(store, recipe)

    recipe_payload = recipe.model_dump(mode="python")
    recipe_payload["output_variable_id"] = "forged_output"
    with pytest.raises(ValidationError, match="identity"):
        type(recipe).model_validate(recipe_payload)

    certificate_payload = materialized.certificate.model_dump(mode="python")
    certificate_payload["effective_authority"] = Decimal("0.99")
    with pytest.raises(ValidationError, match="weakest"):
        type(materialized.certificate).model_validate(certificate_payload)

    series_payload = materialized.series.model_dump(mode="python")
    series_payload["observation_class"] = "observed"
    with pytest.raises(ValidationError):
        type(materialized.series).model_validate(series_payload)


def test_recipe_reopens_every_manifest_input_graph_edge(tmp_path: Path) -> None:
    store, nominal_ref, deflator_ref = _source_artifacts(tmp_path / "cas")
    recipe = build_cpi_derivation_recipe(
        store,
        nominal_ref=nominal_ref,
        deflator_ref=deflator_ref,
        output_variable_id="gdp_real_lcu_2020",
        output_basis=_real_basis(deflator_ref),
        assumptions=_assumptions(),
    )
    authority_edge = next(
        item
        for item in store.get_manifest(nominal_ref.artifact_id).inputs
        if item.role == "authority_evidence"
    )
    authority_blob, _ = store.get_paths(authority_edge.artifact_id)
    authority_blob.write_bytes(b"{}")

    with pytest.raises(DerivationRefusalError) as raised:
        materialize_cpi_real_terms(store, recipe)
    assert raised.value.code is DerivationRefusalCode.INPUT_ARTIFACT_DRIFT
