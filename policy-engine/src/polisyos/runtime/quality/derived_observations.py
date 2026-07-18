"""Certify derived economic observations without promoting them as observed data.

The module owns content-addressed derivation recipes and certificates. It is
deliberately separate from the ordinary acquisition passport/overlay path:
derived values remain typed ``derived`` evidence and require their own consumer
contract.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts, canon
from polisyos.ir import kernel as ir_kernel

if TYPE_CHECKING:
    from collections.abc import Sequence

DERIVATION_SCHEMA_VERSION = "polisyos.runtime.derived_observations.v1"
ECONOMIC_SERIES_KIND = "polisyos.runtime.economic_series"
PRICE_INDEX_SERIES_KIND = "polisyos.runtime.price_index_series"
DERIVED_SERIES_KIND = "polisyos.runtime.derived_economic_series"
DERIVATION_CERTIFICATE_KIND = "polisyos.runtime.derivation_certificate"
_ECONOMIC_SERIES_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.economic-series",
    version="1.0.0",
)
_PRICE_INDEX_SERIES_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.price-index-series",
    version="1.0.0",
)
_DERIVED_SERIES_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.derived-economic-series",
    version="1.0.0",
)
_CERTIFICATE_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.derivation-certificate",
    version="1.0.0",
)
_DERIVATION_PRODUCER = artifacts.ProducerInfo(
    component="polisyos.runtime.quality.derived_observations",
    version="1.0.0",
)
_CANON_SPEC = canon.CanonSpec(exclude_none=False)

AuthorityScore = Annotated[
    ir_kernel.DecimalValue,
    Field(ge=Decimal("0"), le=Decimal("1")),
]


class DerivationRefusalCode(StrEnum):
    """Typed reasons a requested derivation cannot be certified."""

    BASIS_MISMATCH = "basis_mismatch"
    EXACT_YEAR_MISSING = "exact_year_missing"
    BASE_YEAR_MISSING = "base_year_missing"
    INVALID_DEFLATOR = "invalid_deflator"
    INPUT_ARTIFACT_DRIFT = "input_artifact_drift"
    CACHE_ARTIFACT_DRIFT = "cache_artifact_drift"
    CERTIFICATE_DRIFT = "certificate_drift"


class DerivationRefusalError(RuntimeError):
    """Fail-closed, typed refusal for a derivation or certificate read."""

    def __init__(self, code: DerivationRefusalCode, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code.value}: {detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EconomicBasis(_StrictModel):
    """Declare every load-bearing basis property of one monetary series."""

    unit: ir_kernel.MoneyUnit
    price_basis: Literal["nominal", "real"]
    base_year: int | None
    deflator_ref: artifacts.ArtifactID | None
    deflator_version: str | None
    per_capita: bool
    seasonal_adjustment: Literal[
        "not_seasonally_adjusted",
        "seasonally_adjusted",
        "not_applicable",
    ]

    @model_validator(mode="after")
    def _basis_is_explicit_and_coherent(self) -> Self:
        explicit_unit_fields = {"kind", "currency", "nominal_year", "price_base"}
        if not explicit_unit_fields.issubset(self.unit.model_fields_set):
            raise ValueError("money unit fields must be explicit; defaults are not basis evidence")
        if self.price_basis == "nominal":
            if any(
                value is not None
                for value in (self.base_year, self.deflator_ref, self.deflator_version)
            ):
                raise ValueError("nominal basis cannot carry a real-terms deflator declaration")
            return self
        if self.base_year is None or self.deflator_ref is None or not self.deflator_version:
            raise ValueError("real basis requires deflator ref, version, and base year")
        if self.unit.nominal_year != self.base_year:
            raise ValueError("real money unit nominal_year must equal its declared base year")
        if not self.unit.price_base:
            raise ValueError("real money unit requires an explicit price_base")
        return self


class PriceIndexBasis(_StrictModel):
    """Declare the versioned measurement basis of one price-index series."""

    unit: ir_kernel.DimensionlessUnit
    index_id: str = Field(min_length=1)
    index_version: str = Field(min_length=1)
    reference_base_year: int | None = Field(ge=1900, le=2200)
    seasonal_adjustment: Literal[
        "not_seasonally_adjusted",
        "seasonally_adjusted",
        "not_applicable",
    ]

    @model_validator(mode="after")
    def _basis_fields_are_explicit(self) -> Self:
        if not {"kind", "label"}.issubset(self.unit.model_fields_set):
            raise ValueError("price-index unit fields must be explicit")
        return self


class AuthorityProjection(_StrictModel):
    """Content-bound input authority projection used only to cap derivations."""

    effective_score: AuthorityScore
    authority_ref: artifacts.ArtifactID
    verifier_provenance_ref: artifacts.ArtifactID
    authoritative_for: Literal["series_input"]

    @model_validator(mode="after")
    def _verifier_is_independent(self) -> Self:
        if self.authority_ref == self.verifier_provenance_ref:
            raise ValueError("authority and verifier provenance refs must be distinct")
        return self


class SeriesPoint(_StrictModel):
    """One exact-year decimal observation in a derivation input or output."""

    year: int = Field(ge=1900, le=2200)
    value: ir_kernel.DecimalValue

    @field_validator("value")
    @classmethod
    def _value_is_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("series values must be finite")
        return value


def _validate_points(points: tuple[SeriesPoint, ...]) -> None:
    if not points:
        raise ValueError("series requires at least one point")
    years = tuple(point.year for point in points)
    if years != tuple(sorted(set(years))):
        raise ValueError("series years must be unique and strictly increasing")


class EconomicSeries(_StrictModel):
    """Owner-validated nominal or real monetary input series persisted in CAS."""

    schema_version: Literal[DERIVATION_SCHEMA_VERSION] = DERIVATION_SCHEMA_VERSION
    variable_id: str = Field(min_length=1)
    basis: EconomicBasis
    points: tuple[SeriesPoint, ...]
    authority: AuthorityProjection
    observation_class: Literal["observed", "proxy"]

    @model_validator(mode="after")
    def _years_are_exact(self) -> Self:
        _validate_points(self.points)
        return self


class PriceIndexSeries(_StrictModel):
    """Owner-validated price-index input series persisted in CAS."""

    schema_version: Literal[DERIVATION_SCHEMA_VERSION] = DERIVATION_SCHEMA_VERSION
    variable_id: str = Field(min_length=1)
    basis: PriceIndexBasis
    points: tuple[SeriesPoint, ...]
    authority: AuthorityProjection
    observation_class: Literal["observed", "proxy"]

    @model_validator(mode="after")
    def _years_and_values_are_valid(self) -> Self:
        _validate_points(self.points)
        if any(point.value <= 0 for point in self.points):
            raise ValueError("price-index values must be positive")
        return self


class ArtifactInputEdge(_StrictModel):
    """One exact direct-input edge in a CAS manifest projection."""

    role: str = Field(min_length=1)
    artifact_id: artifacts.ArtifactID


class ArtifactContractProjection(_StrictModel):
    """Narrow manifest projection bound into a canonical recipe."""

    artifact_id: artifacts.ArtifactID
    kind: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    producer_component: str = Field(min_length=1)
    producer_version: str = Field(min_length=1)
    input_graph: tuple[ArtifactInputEdge, ...]

    @model_validator(mode="after")
    def _input_graph_is_canonical(self) -> Self:
        keys = tuple((edge.role, str(edge.artifact_id)) for edge in self.input_graph)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("artifact input graph must be unique and sorted")
        return self


class DerivationRecipe(_StrictModel):
    """Canonical CPI-deflation recipe whose identity binds its full input graph."""

    schema_version: Literal[DERIVATION_SCHEMA_VERSION] = DERIVATION_SCHEMA_VERSION
    recipe_id: str = Field(pattern=r"^derivation-recipe:sha256:[0-9a-f]{64}$")
    method_id: Literal["cpi_deflation_exact_year"]
    method_version: Literal["1.0.0"]
    nominal_input: ArtifactContractProjection
    deflator_input: ArtifactContractProjection
    output_variable_id: str = Field(min_length=1)
    nominal_basis: EconomicBasis
    deflator_basis: PriceIndexBasis
    output_basis: EconomicBasis
    base_year: int = Field(ge=1900, le=2200)
    assumptions: tuple[str, ...] = Field(min_length=4)

    @model_validator(mode="after")
    def _recipe_is_canonical(self) -> Self:
        if self.assumptions != tuple(sorted(set(self.assumptions))):
            raise ValueError("derivation assumptions must be unique and sorted")
        required = {
            f"base_year={self.base_year}",
            f"deflator_version={self.deflator_basis.index_version}",
            "exact-year joins; no interpolation",
            "real_t = nominal_t * CPI_base / CPI_t",
        }
        if not required.issubset(self.assumptions):
            raise ValueError("derivation assumptions omit a decisive CPI-deflation property")
        if self.nominal_basis.price_basis != "nominal":
            raise ValueError("CPI deflation input must have nominal basis")
        if self.output_basis.price_basis != "real":
            raise ValueError("CPI deflation output must have real basis")
        if self.output_basis.base_year != self.base_year:
            raise ValueError("output basis and recipe base year differ")
        if self.output_basis.deflator_ref != self.deflator_input.artifact_id:
            raise ValueError("output basis must bind the exact deflator artifact")
        if self.output_basis.deflator_version != self.deflator_basis.index_version:
            raise ValueError("output basis and deflator version differ")
        if self.nominal_basis.unit.currency != self.output_basis.unit.currency:
            raise ValueError("CPI deflation cannot change currency")
        if self.nominal_basis.per_capita != self.output_basis.per_capita:
            raise ValueError("CPI deflation cannot change per-capita basis")
        if self.nominal_basis.seasonal_adjustment != self.output_basis.seasonal_adjustment:
            raise ValueError("CPI deflation cannot change seasonal-adjustment basis")
        expected_id = _identity("derivation-recipe", self.identity_payload())
        if self.recipe_id != expected_id:
            raise ValueError("derivation recipe identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the projection defining this derivation recipe."""

        return {
            key: value
            for key, value in self.model_dump(mode="python").items()
            if key != "recipe_id"
        }


class DerivedEconomicSeries(_StrictModel):
    """Content-addressed output that can never masquerade as an observation."""

    schema_version: Literal[DERIVATION_SCHEMA_VERSION] = DERIVATION_SCHEMA_VERSION
    variable_id: str = Field(min_length=1)
    basis: EconomicBasis
    points: tuple[SeriesPoint, ...]
    recipe_id: str = Field(pattern=r"^derivation-recipe:sha256:[0-9a-f]{64}$")
    source_artifact_ids: tuple[artifacts.ArtifactID, artifacts.ArtifactID]
    observation_class: Literal["derived"]

    @model_validator(mode="after")
    def _series_is_exact(self) -> Self:
        _validate_points(self.points)
        if self.source_artifact_ids[0] == self.source_artifact_ids[1]:
            raise ValueError("nominal and deflator artifacts must be distinct")
        return self


class CertificateInputAuthority(_StrictModel):
    """Authority projection for one exact certificate input."""

    artifact_id: artifacts.ArtifactID
    effective_score: AuthorityScore
    authority_ref: artifacts.ArtifactID
    verifier_provenance_ref: artifacts.ArtifactID


class DerivationCertificate(_StrictModel):
    """Recomputing certificate for one derived series and its authority cap."""

    schema_version: Literal[DERIVATION_SCHEMA_VERSION] = DERIVATION_SCHEMA_VERSION
    certificate_id: str = Field(pattern=r"^derivation-certificate:sha256:[0-9a-f]{64}$")
    recipe: DerivationRecipe
    derived_artifact_id: artifacts.ArtifactID
    input_authorities: tuple[CertificateInputAuthority, CertificateInputAuthority]
    effective_authority: AuthorityScore
    observation_class: Literal["derived"]
    authoritative_for: tuple[Literal["certified_derived_series"], ...]
    may_not_use_for: tuple[
        Literal["observed_series", "source_observation", "acquisition_passport"],
        ...,
    ]

    @model_validator(mode="after")
    def _certificate_is_recomputed(self) -> Self:
        input_ids = tuple(str(item.artifact_id) for item in self.input_authorities)
        if input_ids != tuple(sorted(set(input_ids))):
            raise ValueError("certificate input authorities must be unique and sorted")
        expected_ids = {
            str(self.recipe.nominal_input.artifact_id),
            str(self.recipe.deflator_input.artifact_id),
        }
        if set(input_ids) != expected_ids:
            raise ValueError("certificate authority inputs differ from recipe inputs")
        expected_authority = min(item.effective_score for item in self.input_authorities)
        if self.effective_authority != expected_authority:
            raise ValueError("derived authority must equal the weakest input")
        if self.authoritative_for != ("certified_derived_series",):
            raise ValueError("derivation certificate authority purpose is fixed")
        if self.may_not_use_for != (
            "acquisition_passport",
            "observed_series",
            "source_observation",
        ):
            raise ValueError("derivation certificate must retain all observed-data prohibitions")
        expected_id = _identity("derivation-certificate", self.identity_payload())
        if self.certificate_id != expected_id:
            raise ValueError("derivation certificate identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the projection defining this certificate."""

        return {
            key: value
            for key, value in self.model_dump(mode="python").items()
            if key != "certificate_id"
        }


class DerivationMaterialization(_StrictModel):
    """Result of producing or reopening one verified content-addressed derivation."""

    recipe: DerivationRecipe
    series: DerivedEconomicSeries
    derived_artifact_ref: artifacts.ArtifactRef
    certificate: DerivationCertificate
    certificate_artifact_ref: artifacts.ArtifactRef
    cache_hit: bool


class CertifiedDerivationConsumption(_StrictModel):
    """Consumer-side receipt proving one method read a certified derived series."""

    consumption_id: str = Field(pattern=r"^derivation-consumption:sha256:[0-9a-f]{64}$")
    consumer_method_id: str = Field(min_length=1)
    certificate_artifact_id: artifacts.ArtifactID
    derived_artifact_id: artifacts.ArtifactID
    series: tuple[ir_kernel.DecimalValue, ...]
    observation_class: Literal["derived"]
    cache_verified: Literal[True]

    @model_validator(mode="after")
    def _consumption_identity_is_recomputed(self) -> Self:
        expected = _identity("derivation-consumption", self.identity_payload())
        if self.consumption_id != expected:
            raise ValueError("derivation consumption identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the projection defining this consumer receipt."""

        return {
            key: value
            for key, value in self.model_dump(mode="python").items()
            if key != "consumption_id"
        }


def _identity(prefix: str, payload: object) -> str:
    return f"{prefix}:{canon.fingerprint(payload, prefix=True, canon_spec=_CANON_SPEC)}"


def _canonical_bytes(payload: object) -> bytes:
    return canon.to_canonical_bytes(payload, _CANON_SPEC)


def _sorted_input_refs(refs: Sequence[artifacts.InputRef]) -> list[artifacts.InputRef]:
    return sorted(refs, key=lambda item: (item.role, str(item.artifact_id)))


def _verify_resolvable_ref(
    store: artifacts.FileSystemCAS,
    artifact_id: artifacts.ArtifactID,
) -> None:
    try:
        resolved = store.has(artifact_id) and store.verify(artifact_id).ok
    except (OSError, ValueError):
        resolved = False
    if not resolved:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            str(artifact_id),
        )


def _authority_input_refs(authority: AuthorityProjection) -> list[artifacts.InputRef]:
    return _sorted_input_refs(
        [
            artifacts.InputRef(artifact_id=authority.authority_ref, role="authority_evidence"),
            artifacts.InputRef(
                artifact_id=authority.verifier_provenance_ref,
                role="verifier_provenance",
            ),
        ]
    )


def _persist_source_series(
    store: artifacts.FileSystemCAS,
    series: EconomicSeries | PriceIndexSeries,
    *,
    kind: str,
    schema: artifacts.SchemaInfo,
    producer: artifacts.ProducerInfo,
) -> artifacts.ArtifactRef:
    _verify_resolvable_ref(store, series.authority.authority_ref)
    _verify_resolvable_ref(store, series.authority.verifier_provenance_ref)
    return store.put_bytes(
        _canonical_bytes(series),
        artifacts.PutOptions(
            kind=kind,
            media_type="application/json",
            schema=schema,
            producer=producer,
            inputs=_authority_input_refs(series.authority),
            canon=artifacts.CanonInfo.from_spec(_CANON_SPEC),
        ),
    )


def persist_economic_series(
    store: artifacts.FileSystemCAS,
    series: EconomicSeries,
    *,
    producer: artifacts.ProducerInfo,
) -> artifacts.ArtifactRef:
    """Persist an owner-validated monetary input with its authority input graph."""

    return _persist_source_series(
        store,
        series,
        kind=ECONOMIC_SERIES_KIND,
        schema=_ECONOMIC_SERIES_SCHEMA,
        producer=producer,
    )


def persist_price_index_series(
    store: artifacts.FileSystemCAS,
    series: PriceIndexSeries,
    *,
    producer: artifacts.ProducerInfo,
) -> artifacts.ArtifactRef:
    """Persist an owner-validated price index with its authority input graph."""

    return _persist_source_series(
        store,
        series,
        kind=PRICE_INDEX_SERIES_KIND,
        schema=_PRICE_INDEX_SERIES_SCHEMA,
        producer=producer,
    )


def _manifest_projection(
    store: artifacts.FileSystemCAS,
    artifact_id: artifacts.ArtifactID,
) -> ArtifactContractProjection:
    _verify_resolvable_ref(store, artifact_id)
    try:
        manifest = store.get_manifest(artifact_id)
    except (OSError, ValueError) as exc:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            str(artifact_id),
        ) from exc
    if manifest.artifact_schema is None or manifest.producer is None:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            f"{artifact_id}: schema/producer missing",
        )
    edges = tuple(
        ArtifactInputEdge(role=item.role, artifact_id=item.artifact_id)
        for item in _sorted_input_refs(manifest.inputs)
    )
    return ArtifactContractProjection(
        artifact_id=artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        schema_name=manifest.artifact_schema.name,
        schema_version=manifest.artifact_schema.version,
        producer_component=str(manifest.producer.component),
        producer_version=manifest.producer.version,
        input_graph=edges,
    )


def _load_model[SeriesModelT: (EconomicSeries, PriceIndexSeries)](
    store: artifacts.FileSystemCAS,
    projection: ArtifactContractProjection,
    model: type[SeriesModelT],
    *,
    refusal_code: DerivationRefusalCode,
) -> SeriesModelT:
    current = _manifest_projection(store, projection.artifact_id)
    if current != projection:
        raise DerivationRefusalError(refusal_code, f"{projection.artifact_id}: manifest projection")
    for edge in projection.input_graph:
        try:
            _verify_resolvable_ref(store, edge.artifact_id)
        except DerivationRefusalError as exc:
            raise DerivationRefusalError(
                refusal_code,
                f"{projection.artifact_id}: unresolved input {edge.role}={edge.artifact_id}",
            ) from exc
    try:
        payload = canon.from_canonical_bytes(store.get_bytes(projection.artifact_id))
        return model.model_validate(payload)
    except (OSError, ValueError) as exc:
        raise DerivationRefusalError(refusal_code, str(projection.artifact_id)) from exc


def build_cpi_derivation_recipe(
    store: artifacts.FileSystemCAS,
    *,
    nominal_ref: artifacts.ArtifactRef,
    deflator_ref: artifacts.ArtifactRef,
    output_variable_id: str,
    output_basis: EconomicBasis,
    assumptions: Sequence[str],
) -> DerivationRecipe:
    """Build a canonical recipe from the exact current CAS input projections."""

    if nominal_ref.kind != ECONOMIC_SERIES_KIND or deflator_ref.kind != PRICE_INDEX_SERIES_KIND:
        raise DerivationRefusalError(
            DerivationRefusalCode.BASIS_MISMATCH,
            "recipe inputs do not carry the required economic/index kinds",
        )
    nominal_projection = _manifest_projection(store, nominal_ref.artifact_id)
    deflator_projection = _manifest_projection(store, deflator_ref.artifact_id)
    nominal = _load_model(
        store,
        nominal_projection,
        EconomicSeries,
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    deflator = _load_model(
        store,
        deflator_projection,
        PriceIndexSeries,
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    payload: dict[str, object] = {
        "schema_version": DERIVATION_SCHEMA_VERSION,
        "method_id": "cpi_deflation_exact_year",
        "method_version": "1.0.0",
        "nominal_input": nominal_projection,
        "deflator_input": deflator_projection,
        "output_variable_id": output_variable_id,
        "nominal_basis": nominal.basis,
        "deflator_basis": deflator.basis,
        "output_basis": output_basis,
        "base_year": output_basis.base_year,
        "assumptions": tuple(sorted(assumptions)),
    }
    payload["recipe_id"] = _identity("derivation-recipe", payload)
    try:
        return DerivationRecipe.model_validate(payload)
    except ValueError as exc:
        raise DerivationRefusalError(DerivationRefusalCode.BASIS_MISMATCH, str(exc)) from exc


def _derive_series(
    recipe: DerivationRecipe,
    nominal: EconomicSeries,
    deflator: PriceIndexSeries,
) -> DerivedEconomicSeries:
    if nominal.basis != recipe.nominal_basis or deflator.basis != recipe.deflator_basis:
        raise DerivationRefusalError(
            DerivationRefusalCode.BASIS_MISMATCH,
            "input basis differs from the recipe",
        )
    deflator_by_year = {point.year: point.value for point in deflator.points}
    if recipe.base_year not in deflator_by_year:
        raise DerivationRefusalError(
            DerivationRefusalCode.BASE_YEAR_MISSING,
            str(recipe.base_year),
        )
    missing = tuple(point.year for point in nominal.points if point.year not in deflator_by_year)
    if missing:
        raise DerivationRefusalError(
            DerivationRefusalCode.EXACT_YEAR_MISSING,
            ",".join(str(year) for year in missing),
        )
    base_value = deflator_by_year[recipe.base_year]
    if base_value <= 0:
        raise DerivationRefusalError(DerivationRefusalCode.INVALID_DEFLATOR, str(recipe.base_year))
    points: list[SeriesPoint] = []
    with localcontext() as context:
        context.prec = 50
        for point in nominal.points:
            current_deflator = deflator_by_year[point.year]
            if current_deflator <= 0:
                raise DerivationRefusalError(
                    DerivationRefusalCode.INVALID_DEFLATOR,
                    str(point.year),
                )
            value = point.value * base_value / current_deflator
            points.append(SeriesPoint(year=point.year, value=value))
    return DerivedEconomicSeries(
        variable_id=recipe.output_variable_id,
        basis=recipe.output_basis,
        points=tuple(points),
        recipe_id=recipe.recipe_id,
        source_artifact_ids=(
            recipe.nominal_input.artifact_id,
            recipe.deflator_input.artifact_id,
        ),
        observation_class="derived",
    )


def _expected_output_inputs(recipe: DerivationRecipe) -> list[artifacts.InputRef]:
    return _sorted_input_refs(
        [
            artifacts.InputRef(
                artifact_id=recipe.nominal_input.artifact_id,
                role="nominal_series",
            ),
            artifacts.InputRef(
                artifact_id=recipe.deflator_input.artifact_id,
                role="price_deflator",
            ),
        ]
    )


def _expected_certificate_inputs(
    recipe: DerivationRecipe,
    derived_artifact_id: artifacts.ArtifactID,
) -> list[artifacts.InputRef]:
    return _sorted_input_refs(
        [
            *_expected_output_inputs(recipe),
            artifacts.InputRef(artifact_id=derived_artifact_id, role="derived_series"),
        ]
    )


def _producer_projection(producer: artifacts.ProducerInfo) -> tuple[str, str]:
    return str(producer.component), producer.version


def _verify_cached_artifact(
    store: artifacts.FileSystemCAS,
    *,
    artifact_id: artifacts.ArtifactID,
    expected_bytes: bytes,
    kind: str,
    schema: artifacts.SchemaInfo,
    producer: artifacts.ProducerInfo,
    inputs: Sequence[artifacts.InputRef],
    refusal_code: DerivationRefusalCode,
) -> artifacts.ArtifactRef:
    try:
        if not store.has(artifact_id) or not store.verify(artifact_id).ok:
            raise DerivationRefusalError(refusal_code, f"{artifact_id}: CAS integrity")
        if store.get_bytes(artifact_id) != expected_bytes:
            raise DerivationRefusalError(refusal_code, f"{artifact_id}: bytes")
        manifest = store.get_manifest(artifact_id)
    except DerivationRefusalError:
        raise
    except (OSError, ValueError) as exc:
        raise DerivationRefusalError(refusal_code, str(artifact_id)) from exc
    if (
        manifest.kind != kind
        or manifest.media_type != "application/json"
        or manifest.artifact_schema != schema
        or manifest.producer is None
        or _producer_projection(manifest.producer) != _producer_projection(producer)
        or _sorted_input_refs(manifest.inputs) != _sorted_input_refs(inputs)
    ):
        raise DerivationRefusalError(refusal_code, f"{artifact_id}: manifest contract")
    return artifacts.ArtifactRef(
        artifact_id=artifact_id,
        kind=kind,
        media_type="application/json",
    )


def _put_or_verify(
    store: artifacts.FileSystemCAS,
    *,
    payload: object,
    kind: str,
    schema: artifacts.SchemaInfo,
    inputs: Sequence[artifacts.InputRef],
    refusal_code: DerivationRefusalCode,
) -> tuple[artifacts.ArtifactRef, bool]:
    data = _canonical_bytes(payload)
    artifact_id = artifacts.ArtifactID.from_sha256_hex(canon.content_hash(data))
    cache_hit = store.has(artifact_id)
    if not cache_hit:
        ref = store.put_bytes(
            data,
            artifacts.PutOptions(
                kind=kind,
                media_type="application/json",
                schema=schema,
                producer=_DERIVATION_PRODUCER,
                inputs=_sorted_input_refs(inputs),
                canon=artifacts.CanonInfo.from_spec(_CANON_SPEC),
            ),
        )
        if ref.artifact_id != artifact_id:
            raise DerivationRefusalError(refusal_code, "CAS returned a different content identity")
    return (
        _verify_cached_artifact(
            store,
            artifact_id=artifact_id,
            expected_bytes=data,
            kind=kind,
            schema=schema,
            producer=_DERIVATION_PRODUCER,
            inputs=inputs,
            refusal_code=refusal_code,
        ),
        cache_hit,
    )


def _certificate(
    recipe: DerivationRecipe,
    nominal: EconomicSeries,
    deflator: PriceIndexSeries,
    derived_artifact_id: artifacts.ArtifactID,
) -> DerivationCertificate:
    authorities = tuple(
        sorted(
            (
                CertificateInputAuthority(
                    artifact_id=recipe.nominal_input.artifact_id,
                    effective_score=nominal.authority.effective_score,
                    authority_ref=nominal.authority.authority_ref,
                    verifier_provenance_ref=nominal.authority.verifier_provenance_ref,
                ),
                CertificateInputAuthority(
                    artifact_id=recipe.deflator_input.artifact_id,
                    effective_score=deflator.authority.effective_score,
                    authority_ref=deflator.authority.authority_ref,
                    verifier_provenance_ref=deflator.authority.verifier_provenance_ref,
                ),
            ),
            key=lambda item: str(item.artifact_id),
        )
    )
    payload: dict[str, object] = {
        "schema_version": DERIVATION_SCHEMA_VERSION,
        "recipe": recipe,
        "derived_artifact_id": derived_artifact_id,
        "input_authorities": authorities,
        "effective_authority": min(item.effective_score for item in authorities),
        "observation_class": "derived",
        "authoritative_for": ("certified_derived_series",),
        "may_not_use_for": (
            "acquisition_passport",
            "observed_series",
            "source_observation",
        ),
    }
    payload["certificate_id"] = _identity("derivation-certificate", payload)
    return DerivationCertificate.model_validate(payload)


def materialize_cpi_real_terms(
    store: artifacts.FileSystemCAS,
    recipe: DerivationRecipe,
) -> DerivationMaterialization:
    """Produce or verify one exact-year CPI derivation and its certificate."""

    nominal = _load_model(
        store,
        recipe.nominal_input,
        EconomicSeries,
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    deflator = _load_model(
        store,
        recipe.deflator_input,
        PriceIndexSeries,
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    series = _derive_series(recipe, nominal, deflator)
    derived_ref, cache_hit = _put_or_verify(
        store,
        payload=series,
        kind=DERIVED_SERIES_KIND,
        schema=_DERIVED_SERIES_SCHEMA,
        inputs=_expected_output_inputs(recipe),
        refusal_code=DerivationRefusalCode.CACHE_ARTIFACT_DRIFT,
    )
    certificate = _certificate(recipe, nominal, deflator, derived_ref.artifact_id)
    certificate_ref, _ = _put_or_verify(
        store,
        payload=certificate,
        kind=DERIVATION_CERTIFICATE_KIND,
        schema=_CERTIFICATE_SCHEMA,
        inputs=_expected_certificate_inputs(recipe, derived_ref.artifact_id),
        refusal_code=DerivationRefusalCode.CERTIFICATE_DRIFT,
    )
    return DerivationMaterialization(
        recipe=recipe,
        series=series,
        derived_artifact_ref=derived_ref,
        certificate=certificate,
        certificate_artifact_ref=certificate_ref,
        cache_hit=cache_hit,
    )


def consume_certified_derivation(
    store: artifacts.FileSystemCAS,
    *,
    certificate_ref: artifacts.ArtifactRef,
    consumer_method_id: str,
) -> CertifiedDerivationConsumption:
    """Reopen the certificate graph and return one method-scoped series receipt.

    The consumer path re-derives the expected bytes from both inputs before it
    exposes values. A present certificate or a bare ``CAS.has`` result is never
    sufficient.
    """

    if not consumer_method_id.strip():
        raise ValueError("consumer_method_id must be non-empty")
    if certificate_ref.kind != DERIVATION_CERTIFICATE_KIND:
        raise DerivationRefusalError(
            DerivationRefusalCode.CERTIFICATE_DRIFT,
            "certificate ref carries the wrong artifact kind",
        )
    try:
        certificate_payload = canon.from_canonical_bytes(
            store.get_bytes(certificate_ref.artifact_id)
        )
        certificate = DerivationCertificate.model_validate(certificate_payload)
    except (OSError, ValueError) as exc:
        raise DerivationRefusalError(
            DerivationRefusalCode.CERTIFICATE_DRIFT,
            str(certificate_ref.artifact_id),
        ) from exc
    _verify_cached_artifact(
        store,
        artifact_id=certificate_ref.artifact_id,
        expected_bytes=_canonical_bytes(certificate),
        kind=DERIVATION_CERTIFICATE_KIND,
        schema=_CERTIFICATE_SCHEMA,
        producer=_DERIVATION_PRODUCER,
        inputs=_expected_certificate_inputs(
            certificate.recipe,
            certificate.derived_artifact_id,
        ),
        refusal_code=DerivationRefusalCode.CERTIFICATE_DRIFT,
    )
    nominal = _load_model(
        store,
        certificate.recipe.nominal_input,
        EconomicSeries,
        refusal_code=DerivationRefusalCode.CERTIFICATE_DRIFT,
    )
    deflator = _load_model(
        store,
        certificate.recipe.deflator_input,
        PriceIndexSeries,
        refusal_code=DerivationRefusalCode.CERTIFICATE_DRIFT,
    )
    expected_series = _derive_series(certificate.recipe, nominal, deflator)
    expected_bytes = _canonical_bytes(expected_series)
    expected_artifact_id = artifacts.ArtifactID.from_sha256_hex(canon.content_hash(expected_bytes))
    if certificate.derived_artifact_id != expected_artifact_id:
        raise DerivationRefusalError(
            DerivationRefusalCode.CERTIFICATE_DRIFT,
            "certificate output differs from recomputed recipe output",
        )
    _verify_cached_artifact(
        store,
        artifact_id=certificate.derived_artifact_id,
        expected_bytes=expected_bytes,
        kind=DERIVED_SERIES_KIND,
        schema=_DERIVED_SERIES_SCHEMA,
        producer=_DERIVATION_PRODUCER,
        inputs=_expected_output_inputs(certificate.recipe),
        refusal_code=DerivationRefusalCode.CACHE_ARTIFACT_DRIFT,
    )
    expected_certificate = _certificate(
        certificate.recipe,
        nominal,
        deflator,
        certificate.derived_artifact_id,
    )
    if certificate != expected_certificate:
        raise DerivationRefusalError(
            DerivationRefusalCode.CERTIFICATE_DRIFT,
            "certificate projection differs from recomputed authority and recipe",
        )
    payload: dict[str, object] = {
        "consumer_method_id": consumer_method_id,
        "certificate_artifact_id": certificate_ref.artifact_id,
        "derived_artifact_id": certificate.derived_artifact_id,
        "series": tuple(point.value for point in expected_series.points),
        "observation_class": "derived",
        "cache_verified": True,
    }
    payload["consumption_id"] = _identity("derivation-consumption", payload)
    return CertifiedDerivationConsumption.model_validate(payload)


__all__ = [
    "DERIVATION_CERTIFICATE_KIND",
    "DERIVATION_SCHEMA_VERSION",
    "DERIVED_SERIES_KIND",
    "ECONOMIC_SERIES_KIND",
    "PRICE_INDEX_SERIES_KIND",
    "ArtifactContractProjection",
    "ArtifactInputEdge",
    "AuthorityProjection",
    "CertificateInputAuthority",
    "CertifiedDerivationConsumption",
    "DerivationCertificate",
    "DerivationMaterialization",
    "DerivationRecipe",
    "DerivationRefusalCode",
    "DerivationRefusalError",
    "DerivedEconomicSeries",
    "EconomicBasis",
    "EconomicSeries",
    "PriceIndexBasis",
    "PriceIndexSeries",
    "SeriesPoint",
    "build_cpi_derivation_recipe",
    "consume_certified_derivation",
    "materialize_cpi_real_terms",
    "persist_economic_series",
    "persist_price_index_series",
]
