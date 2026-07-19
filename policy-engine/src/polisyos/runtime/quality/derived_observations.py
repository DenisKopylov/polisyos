"""Certify data-defined derived series without promoting them as observations.

Transform families are owner data interpreted by a deliberately small arithmetic
language.  The runtime owns validation, content addressing, cache verification,
authority monotonicity, and the observed/derived boundary; it does not own a
catalog of economic transform instances.

The former v1 CPI-specific public names remain importable as a typed refusal
boundary.  V1 artifacts cannot be authority-preservingly upgraded here: their
source manifests allowed caller-selected producers and their recipe semantics
require the removed instance engine.  Callers must re-admit source evidence and
build a v2 registry-backed recipe instead of replaying v1 as generic authority.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, Never, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from polisyos.core import artifacts, canon
from polisyos.ir import api as ir_api

if TYPE_CHECKING:
    from collections.abc import Sequence

DERIVATION_SCHEMA_VERSION = "polisyos.runtime.derived_observations.v2"
LEGACY_DERIVATION_SCHEMA_VERSION = "polisyos.runtime.derived_observations.v1"
SOURCE_SERIES_KIND = "polisyos.runtime.derivation_source_series"
ECONOMIC_SERIES_KIND = "polisyos.runtime.economic_series"
PRICE_INDEX_SERIES_KIND = "polisyos.runtime.price_index_series"
TRANSFORM_FAMILY_REGISTRY_KIND = "polisyos.runtime.transform_family_registry"
DERIVED_SERIES_KIND = "polisyos.runtime.derived_economic_series"
DERIVATION_CERTIFICATE_KIND = "polisyos.runtime.derivation_certificate"
_SOURCE_SERIES_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.derivation-source-series",
    version="2.0.0",
)
_TRANSFORM_FAMILY_REGISTRY_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.transform-family-registry",
    version="2.0.0",
)
_DERIVED_SERIES_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.derived-economic-series",
    version="2.0.0",
)
_CERTIFICATE_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.derivation-certificate",
    version="2.0.0",
)
_DERIVATION_PRODUCER = artifacts.ProducerInfo(
    component="polisyos.runtime.quality.derived_observations",
    version="2.0.0",
)
_SOURCE_SERIES_PRODUCER = _DERIVATION_PRODUCER
_CANON_SPEC = canon.CanonSpec(exclude_none=False)
_DEFAULT_UNITS_REGISTRY = ir_api.resolve_lazy_export(
    "DEFAULT_UNITS_REGISTRY",
    namespace={},
    exports=ir_api.KERNEL_FACADE_EXPORTS,
)


def _reject_float(value: object) -> object:
    if isinstance(value, float):
        raise ValueError("floating-point input is not exact decimal evidence")
    return value


ExactDecimal = Annotated[Decimal, BeforeValidator(_reject_float)]
AuthorityScore = Annotated[
    ExactDecimal,
    Field(ge=Decimal("0"), le=Decimal("1")),
]


class DerivationRefusalCode(StrEnum):
    """Typed reason classes for a refused derivation or certificate read."""

    BASIS_MISMATCH = "basis_mismatch"
    EXACT_YEAR_MISSING = "exact_year_missing"
    PARAMETER_DERIVATION_FAILED = "parameter_derivation_failed"
    INPUT_VALUE_CONSTRAINT = "input_value_constraint"
    ARITHMETIC_DOMAIN_ERROR = "arithmetic_domain_error"
    INPUT_ARTIFACT_DRIFT = "input_artifact_drift"
    CACHE_ARTIFACT_DRIFT = "cache_artifact_drift"
    CERTIFICATE_DRIFT = "certificate_drift"
    LEGACY_SCHEMA_UNSUPPORTED = "legacy_schema_unsupported"


class DerivationRefusalReason(StrEnum):
    """Machine-readable detail below a refusal class."""

    NO_CERTIFIED_TRANSFORM = "no_certified_transform"
    AMBIGUOUS_CERTIFIED_TRANSFORM = "ambiguous_certified_transform"


class DerivationRefusalError(RuntimeError):
    """Fail-closed refusal carrying a stable class and optional reason."""

    def __init__(
        self,
        code: DerivationRefusalCode,
        detail: str,
        *,
        reason: DerivationRefusalReason | None = None,
    ) -> None:
        self.code = code
        self.reason = reason
        self.detail = detail
        suffix = f"/{reason.value}" if reason is not None else ""
        super().__init__(f"{code.value}{suffix}: {detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _raise_legacy_v1_unsupported(surface: str) -> Never:
    raise DerivationRefusalError(
        DerivationRefusalCode.LEGACY_SCHEMA_UNSUPPORTED,
        f"{surface}: re-admit sources and rebuild through a v2 transform registry",
    )


class _UnsupportedLegacyV1Contract:
    """Import-compatible boundary for removed CPI-specific v1 DTOs."""

    def __new__(cls, *_args: object, **_kwargs: object) -> Never:
        _raise_legacy_v1_unsupported(cls.__name__)

    @classmethod
    def model_validate(cls, _payload: object) -> Never:
        """Typed-refuse parsing rather than treating v1 fields as v2 authority."""

        _raise_legacy_v1_unsupported(cls.__name__)


class BasisAttribute(_StrictModel):
    """One named, owner-declared component of a series basis."""

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)


class BasisSignature(_StrictModel):
    """Vocabulary-neutral, exact signature used to resolve transform families."""

    quantity_kind: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    attributes: tuple[BasisAttribute, ...] = ()

    @model_validator(mode="after")
    def _attributes_are_canonical(self) -> Self:
        keys = tuple(item.name for item in self.attributes)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("basis attributes must be unique and sorted")
        return self

    def attribute(self, name: str) -> str | None:
        """Return one declared attribute without assigning vocabulary meaning."""

        return next((item.value for item in self.attributes if item.name == name), None)


class AuthorityProjection(_StrictModel):
    """Content-bound input authority used solely as a derivation ceiling."""

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
    """One exact-year decimal point in an input or output series."""

    year: int = Field(ge=1900, le=2200)
    value: ExactDecimal

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


class SourceSeries(_StrictModel):
    """Owner-validated observed or proxy input persisted in CAS."""

    schema_version: Literal[DERIVATION_SCHEMA_VERSION] = DERIVATION_SCHEMA_VERSION
    variable_id: str = Field(min_length=1)
    basis: BasisSignature
    points: tuple[SeriesPoint, ...]
    authority: AuthorityProjection
    observation_class: Literal["observed", "proxy"]

    @model_validator(mode="after")
    def _years_are_exact(self) -> Self:
        _validate_points(self.points)
        return self


ValueConstraint = Literal["nonnegative", "nonzero", "positive"]


class TransformInputSpec(_StrictModel):
    """Data-declared role, basis, and numeric preconditions for one input."""

    role: str = Field(min_length=1)
    basis: BasisSignature
    value_constraints: tuple[ValueConstraint, ...] = ()

    @model_validator(mode="after")
    def _constraints_are_canonical(self) -> Self:
        if self.value_constraints != tuple(sorted(set(self.value_constraints))):
            raise ValueError("input value constraints must be unique and sorted")
        return self


ArithmeticOperator = Literal[
    "current_value",
    "value_at_parameter",
    "parameter",
    "constant",
    "add",
    "subtract",
    "multiply",
    "divide",
]


class ArithmeticExpression(_StrictModel):
    """One node in the closed, non-Turing-complete arithmetic language."""

    operator: ArithmeticOperator
    role: str | None = None
    parameter_name: str | None = None
    constant_value: ExactDecimal | None = None
    operands: tuple[ArithmeticExpression, ...] = ()

    @model_validator(mode="after")
    def _node_shape_is_closed(self) -> Self:
        leaf_shapes: dict[str, tuple[bool, bool, bool]] = {
            "current_value": (True, False, False),
            "value_at_parameter": (True, True, False),
            "parameter": (False, True, False),
            "constant": (False, False, True),
        }
        if self.operator in leaf_shapes:
            role, parameter, constant = leaf_shapes[self.operator]
            if (
                (self.role is not None) != role
                or (self.parameter_name is not None) != parameter
                or (self.constant_value is not None) != constant
                or self.operands
            ):
                raise ValueError(f"invalid {self.operator} expression shape")
            return self
        if (
            self.role is not None
            or self.parameter_name is not None
            or self.constant_value is not None
            or len(self.operands) != 2
        ):
            raise ValueError(f"{self.operator} requires exactly two operands")
        return self

    def referenced_roles(self) -> frozenset[str]:
        """Return all source roles addressed by this expression."""

        roles = {self.role} if self.role is not None else set()
        for operand in self.operands:
            roles.update(operand.referenced_roles())
        return frozenset(roles)

    def referenced_parameters(self) -> frozenset[str]:
        """Return all derived parameters addressed by this expression."""

        names = {self.parameter_name} if self.parameter_name is not None else set()
        for operand in self.operands:
            names.update(operand.referenced_parameters())
        return frozenset(names)


ParameterOperator = Literal["literal", "lower_median_common_year"]


class ParameterRule(_StrictModel):
    """Data-declared deterministic rule for one recipe parameter."""

    name: str = Field(min_length=1)
    operator: ParameterOperator
    input_roles: tuple[str, ...] = ()
    literal_value: ExactDecimal | None = None

    @model_validator(mode="after")
    def _rule_shape_is_closed(self) -> Self:
        if self.input_roles != tuple(sorted(set(self.input_roles))):
            raise ValueError("parameter input roles must be unique and sorted")
        if self.operator == "literal":
            if self.literal_value is None or self.input_roles:
                raise ValueError("literal parameter requires only literal_value")
        elif self.literal_value is not None or not self.input_roles:
            raise ValueError("common-year parameter requires one or more input roles")
        return self


class DerivedParameter(_StrictModel):
    """One recomputed parameter bound into a recipe identity."""

    name: str = Field(min_length=1)
    rule: ParameterRule
    value: ExactDecimal


class AssumptionRule(_StrictModel):
    """Data rule resolving a certificate assumption from a literal or parameter."""

    name: str = Field(min_length=1)
    literal_value: str | None = Field(default=None, min_length=1)
    parameter_name: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _has_exactly_one_source(self) -> Self:
        if (self.literal_value is None) == (self.parameter_name is None):
            raise ValueError("assumption requires exactly one value source")
        return self


class ResolvedAssumption(_StrictModel):
    """One explicit assumption carried by the recipe and certificate."""

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)


class BasisParameterBinding(_StrictModel):
    """Require an output-basis attribute to equal a derived parameter."""

    parameter_name: str = Field(min_length=1)
    output_attribute: str = Field(min_length=1)


class TransformFamily(_StrictModel):
    """Complete data-owned contract for one transform family."""

    family_id: str = Field(min_length=1)
    method_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    input_specs: tuple[TransformInputSpec, ...] = Field(min_length=1)
    output_basis: BasisSignature
    year_domain_role: str = Field(min_length=1)
    parameter_rules: tuple[ParameterRule, ...] = ()
    output_parameter_bindings: tuple[BasisParameterBinding, ...] = ()
    expression: ArithmeticExpression
    assumption_rules: tuple[AssumptionRule, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _family_is_closed_and_self_consistent(self) -> Self:
        roles = tuple(item.role for item in self.input_specs)
        if roles != tuple(sorted(set(roles))):
            raise ValueError("transform input roles must be unique and sorted")
        if self.year_domain_role not in roles:
            raise ValueError("year-domain role must be one of the transform inputs")
        parameter_names = tuple(item.name for item in self.parameter_rules)
        if parameter_names != tuple(sorted(set(parameter_names))):
            raise ValueError("parameter rules must be unique and sorted")
        assumption_names = tuple(item.name for item in self.assumption_rules)
        if assumption_names != tuple(sorted(set(assumption_names))):
            raise ValueError("assumption rules must be unique and sorted")
        bindings = tuple(
            (item.output_attribute, item.parameter_name) for item in self.output_parameter_bindings
        )
        if bindings != tuple(sorted(set(bindings))):
            raise ValueError("output parameter bindings must be unique and sorted")
        role_set = set(roles)
        parameter_set = set(parameter_names)
        rule_roles = {role for rule in self.parameter_rules for role in rule.input_roles}
        if not rule_roles.issubset(role_set):
            raise ValueError("parameter rule references an undeclared input role")
        if not self.expression.referenced_roles().issubset(role_set):
            raise ValueError("expression references an undeclared input role")
        if not self.expression.referenced_parameters().issubset(parameter_set):
            raise ValueError("expression references an undeclared parameter")
        assumption_parameters = {
            item.parameter_name for item in self.assumption_rules if item.parameter_name is not None
        }
        if not assumption_parameters.issubset(parameter_set):
            raise ValueError("assumption references an undeclared parameter")
        binding_parameters = {item.parameter_name for item in self.output_parameter_bindings}
        if not binding_parameters.issubset(parameter_set):
            raise ValueError("basis binding references an undeclared parameter")
        output_attributes = {item.name for item in self.output_basis.attributes}
        if any(
            item.output_attribute not in output_attributes
            for item in self.output_parameter_bindings
        ):
            raise ValueError("basis binding references an undeclared output attribute")
        for binding in self.output_parameter_bindings:
            expected_template = f"${{{binding.parameter_name}}}"
            if self.output_basis.attribute(binding.output_attribute) != expected_template:
                raise ValueError(
                    "parameter-bound output attributes must use their declared template"
                )
        return self


def _output_basis_matches_family(
    family: TransformFamily,
    output_basis: BasisSignature,
) -> bool:
    if (
        family.output_basis.quantity_kind != output_basis.quantity_kind
        or family.output_basis.unit != output_basis.unit
    ):
        return False
    family_attributes = {item.name: item.value for item in family.output_basis.attributes}
    output_attributes = {item.name: item.value for item in output_basis.attributes}
    if set(family_attributes) != set(output_attributes):
        return False
    dynamic_attributes = {item.output_attribute for item in family.output_parameter_bindings}
    return all(
        name in dynamic_attributes or output_attributes[name] == value
        for name, value in family_attributes.items()
    )


class TransformFamilyRegistry(_StrictModel):
    """Owner-supplied family registry; new families require data, not code."""

    families: tuple[TransformFamily, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _families_are_unambiguous(self) -> Self:
        identities = tuple((item.family_id, item.method_version) for item in self.families)
        if identities != tuple(sorted(identities)):
            raise ValueError("transform families must be sorted by identity")
        if len(identities) != len(set(identities)):
            raise ValueError("transform family identities must be unique")
        return self

    def resolve(
        self,
        *,
        input_bases: Mapping[str, BasisSignature],
        output_basis: BasisSignature,
        family_id: str | None = None,
        method_version: str | None = None,
    ) -> TransformFamily:
        """Resolve an exact declared basis edge or fail closed with a typed reason."""

        candidates = [
            family
            for family in self.families
            if (family_id is None or family.family_id == family_id)
            and (method_version is None or family.method_version == method_version)
            and _output_basis_matches_family(family, output_basis)
            and {item.role for item in family.input_specs} == set(input_bases)
            and all(input_bases[item.role] == item.basis for item in family.input_specs)
        ]
        if not candidates:
            raise DerivationRefusalError(
                DerivationRefusalCode.BASIS_MISMATCH,
                family_id or "declared input/output basis edge",
                reason=DerivationRefusalReason.NO_CERTIFIED_TRANSFORM,
            )
        if len(candidates) != 1:
            raise DerivationRefusalError(
                DerivationRefusalCode.BASIS_MISMATCH,
                ",".join(sorted(item.family_id for item in candidates)),
                reason=DerivationRefusalReason.AMBIGUOUS_CERTIFIED_TRANSFORM,
            )
        return candidates[0]

    def resolve_for_inputs(
        self,
        *,
        input_bases: Mapping[str, BasisSignature],
        family_id: str | None = None,
        method_version: str | None = None,
    ) -> TransformFamily:
        """Resolve a family before its parameterized output basis is materialized."""

        candidates = [
            family
            for family in self.families
            if (family_id is None or family.family_id == family_id)
            and (method_version is None or family.method_version == method_version)
            and {item.role for item in family.input_specs} == set(input_bases)
            and all(input_bases[item.role] == item.basis for item in family.input_specs)
        ]
        if not candidates:
            raise DerivationRefusalError(
                DerivationRefusalCode.BASIS_MISMATCH,
                family_id or "declared input basis edge",
                reason=DerivationRefusalReason.NO_CERTIFIED_TRANSFORM,
            )
        if len(candidates) != 1:
            raise DerivationRefusalError(
                DerivationRefusalCode.BASIS_MISMATCH,
                ",".join(sorted(item.family_id for item in candidates)),
                reason=DerivationRefusalReason.AMBIGUOUS_CERTIFIED_TRANSFORM,
            )
        return candidates[0]


def load_transform_family_registry(
    source: str | Path | Mapping[str, object],
) -> TransformFamilyRegistry:
    """Load a strict registry from TOML or an already-decoded owner mapping."""

    payload: Mapping[str, object]
    if isinstance(source, Mapping):
        payload = source
    else:
        payload = tomllib.loads(Path(source).read_text(encoding="utf-8"))
    registry = TransformFamilyRegistry.model_validate(payload)
    _require_registered_basis_units(_registry_bases(registry))
    return registry


class ArtifactInputEdge(_StrictModel):
    """One exact direct-input edge in a CAS manifest."""

    role: str = Field(min_length=1)
    artifact_id: artifacts.ArtifactID


class ArtifactContractProjection(_StrictModel):
    """Contract fields plus a hash binding the stable manifest projection.

    ``ArtifactManifest.created_at`` is operational evidence and is deliberately
    excluded from recipe identity.  A cold rebuild of identical source bytes
    must therefore produce the same recipe even when its CAS sidecar is written
    at a different wall-clock instant.
    """

    artifact_id: artifacts.ArtifactID
    kind: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    producer_component: str = Field(min_length=1)
    producer_version: str = Field(min_length=1)
    input_graph: tuple[ArtifactInputEdge, ...]
    manifest_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _input_graph_is_canonical(self) -> Self:
        keys = tuple((edge.role, str(edge.artifact_id)) for edge in self.input_graph)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("artifact input graph must be unique and sorted")
        return self


class RecipeInput(_StrictModel):
    """One role-bound input basis and complete CAS contract projection."""

    role: str = Field(min_length=1)
    artifact: ArtifactContractProjection
    basis: BasisSignature


class DerivationRecipe(_StrictModel):
    """Canonical recipe binding family data, parameters, and every input."""

    schema_version: Literal[DERIVATION_SCHEMA_VERSION] = DERIVATION_SCHEMA_VERSION
    recipe_id: str = Field(pattern=r"^derivation-recipe:sha256:[0-9a-f]{64}$")
    registry_artifact: ArtifactContractProjection
    family: TransformFamily
    method_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    inputs: tuple[RecipeInput, ...] = Field(min_length=1)
    output_variable_id: str = Field(min_length=1)
    output_basis: BasisSignature
    parameters: tuple[DerivedParameter, ...]
    assumptions: tuple[ResolvedAssumption, ...] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _legacy_recipe_is_typed_refused(cls, payload: object) -> object:
        if (
            isinstance(payload, Mapping)
            and payload.get("schema_version") == LEGACY_DERIVATION_SCHEMA_VERSION
        ):
            _raise_legacy_v1_unsupported(cls.__name__)
        return payload

    @model_validator(mode="after")
    def _recipe_is_recomputed(self) -> Self:
        if (self.method_id, self.method_version) != (
            self.family.method_id,
            self.family.method_version,
        ):
            raise ValueError("recipe method differs from its family definition")
        roles = tuple(item.role for item in self.inputs)
        if roles != tuple(sorted(set(roles))):
            raise ValueError("recipe inputs must be unique and sorted by role")
        spec_by_role = {item.role: item for item in self.family.input_specs}
        if set(roles) != set(spec_by_role):
            raise ValueError("recipe inputs differ from family roles")
        if any(item.basis != spec_by_role[item.role].basis for item in self.inputs):
            raise ValueError("recipe input basis differs from family definition")
        if not _output_basis_matches_family(self.family, self.output_basis):
            raise ValueError("recipe output basis differs from family template")
        parameter_names = tuple(item.name for item in self.parameters)
        if parameter_names != tuple(sorted(set(parameter_names))):
            raise ValueError("recipe parameters must be unique and sorted")
        if parameter_names != tuple(item.name for item in self.family.parameter_rules):
            raise ValueError("recipe parameters differ from family rules")
        if any(
            item.rule != self.family.parameter_rules[index]
            for index, item in enumerate(self.parameters)
        ):
            raise ValueError("recipe parameter rule differs from family definition")
        expected_assumptions = _resolve_assumptions(self.family, self.parameters)
        if self.assumptions != expected_assumptions:
            raise ValueError("recipe assumptions differ from family rules")
        _validate_output_parameter_bindings(
            self.family,
            self.parameters,
            self.output_basis,
        )
        if self.recipe_id != _identity("derivation-recipe", self.identity_payload()):
            raise ValueError("derivation recipe identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the complete projection defining this recipe."""

        return {
            key: value
            for key, value in self.model_dump(mode="python").items()
            if key != "recipe_id"
        }


class DerivedSeries(_StrictModel):
    """Content-addressed output that cannot validate as an observation."""

    schema_version: Literal[DERIVATION_SCHEMA_VERSION] = DERIVATION_SCHEMA_VERSION
    variable_id: str = Field(min_length=1)
    basis: BasisSignature
    points: tuple[SeriesPoint, ...]
    recipe_id: str = Field(pattern=r"^derivation-recipe:sha256:[0-9a-f]{64}$")
    source_artifact_ids: tuple[artifacts.ArtifactID, ...] = Field(min_length=1)
    observation_class: Literal["derived"]

    @model_validator(mode="after")
    def _series_is_exact(self) -> Self:
        _validate_points(self.points)
        source_ids = tuple(str(item) for item in self.source_artifact_ids)
        if source_ids != tuple(sorted(set(source_ids))):
            raise ValueError("derived source artifacts must be unique and sorted")
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
    input_authorities: tuple[CertificateInputAuthority, ...] = Field(min_length=1)
    effective_authority: AuthorityScore
    observation_class: Literal["derived"]
    authoritative_for: tuple[Literal["certified_derived_series"], ...]
    may_not_use_for: tuple[
        Literal["observed_series", "source_observation", "acquisition_passport"],
        ...,
    ]

    @model_validator(mode="before")
    @classmethod
    def _legacy_certificate_is_typed_refused(cls, payload: object) -> object:
        if (
            isinstance(payload, Mapping)
            and payload.get("schema_version") == LEGACY_DERIVATION_SCHEMA_VERSION
        ):
            _raise_legacy_v1_unsupported(cls.__name__)
        return payload

    @model_validator(mode="after")
    def _certificate_is_recomputed(self) -> Self:
        input_ids = tuple(str(item.artifact_id) for item in self.input_authorities)
        if input_ids != tuple(sorted(set(input_ids))):
            raise ValueError("certificate input authorities must be unique and sorted")
        expected_ids = {str(item.artifact.artifact_id) for item in self.recipe.inputs}
        if set(input_ids) != expected_ids:
            raise ValueError("certificate authority inputs differ from recipe inputs")
        if self.effective_authority != min(item.effective_score for item in self.input_authorities):
            raise ValueError("derived authority must equal the weakest input")
        if self.authoritative_for != ("certified_derived_series",):
            raise ValueError("derivation certificate authority purpose is fixed")
        if self.may_not_use_for != (
            "acquisition_passport",
            "observed_series",
            "source_observation",
        ):
            raise ValueError("derivation certificate must retain observed-data prohibitions")
        if self.certificate_id != _identity(
            "derivation-certificate",
            self.identity_payload(),
        ):
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
    """Result of producing or reopening one verified derivation."""

    recipe: DerivationRecipe
    series: DerivedSeries
    derived_artifact_ref: artifacts.ArtifactRef
    certificate: DerivationCertificate
    certificate_artifact_ref: artifacts.ArtifactRef
    cache_hit: bool


class CertifiedDerivationConsumption(_StrictModel):
    """Consumer receipt proving a method read a certified derived series."""

    consumption_id: str = Field(pattern=r"^derivation-consumption:sha256:[0-9a-f]{64}$")
    consumer_method_id: str = Field(min_length=1)
    certificate_artifact_id: artifacts.ArtifactID
    derived_artifact_id: artifacts.ArtifactID
    series: tuple[ExactDecimal, ...]
    observation_class: Literal["derived"]
    cache_verified: Literal[True]

    @model_validator(mode="after")
    def _consumption_identity_is_recomputed(self) -> Self:
        if self.consumption_id != _identity(
            "derivation-consumption",
            self.identity_payload(),
        ):
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


def _require_registered_basis_units(bases: Iterable[BasisSignature]) -> None:
    units = tuple(basis.unit for basis in bases)
    unknown = tuple(sorted(set(units) - set(_DEFAULT_UNITS_REGISTRY.units)))
    if unknown:
        raise DerivationRefusalError(
            DerivationRefusalCode.BASIS_MISMATCH,
            "unregistered basis unit(s): " + ",".join(unknown),
            reason=DerivationRefusalReason.NO_CERTIFIED_TRANSFORM,
        )


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


def persist_source_series(
    store: artifacts.FileSystemCAS,
    series: SourceSeries,
) -> artifacts.ArtifactRef:
    """Persist one owner-validated source with its authority input graph."""

    _require_registered_basis_units((series.basis,))
    _verify_resolvable_ref(store, series.authority.authority_ref)
    _verify_resolvable_ref(store, series.authority.verifier_provenance_ref)
    return store.put_bytes(
        _canonical_bytes(series),
        artifacts.PutOptions(
            kind=SOURCE_SERIES_KIND,
            media_type="application/json",
            schema=_SOURCE_SERIES_SCHEMA,
            producer=_SOURCE_SERIES_PRODUCER,
            inputs=_authority_input_refs(series.authority),
            canon=artifacts.CanonInfo.from_spec(_CANON_SPEC),
        ),
    )


def _manifest_sha256(manifest: artifacts.ArtifactManifest) -> str:
    """Hash every manifest field except the operational creation timestamp."""

    return canon.fingerprint(
        manifest.model_dump(mode="json", by_alias=True, exclude={"created_at"}),
        prefix=True,
        canon_spec=_CANON_SPEC,
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
    return ArtifactContractProjection(
        artifact_id=artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        schema_name=manifest.artifact_schema.name,
        schema_version=manifest.artifact_schema.version,
        producer_component=str(manifest.producer.component),
        producer_version=manifest.producer.version,
        input_graph=tuple(
            ArtifactInputEdge(role=item.role, artifact_id=item.artifact_id)
            for item in _sorted_input_refs(manifest.inputs)
        ),
        manifest_sha256=_manifest_sha256(manifest),
    )


def _expected_input_edges(
    refs: Sequence[artifacts.InputRef],
) -> tuple[ArtifactInputEdge, ...]:
    return tuple(
        ArtifactInputEdge(role=item.role, artifact_id=item.artifact_id)
        for item in _sorted_input_refs(refs)
    )


def _verify_intake_contract(
    projection: ArtifactContractProjection,
    *,
    kind: str,
    schema: artifacts.SchemaInfo,
    producer: artifacts.ProducerInfo,
    inputs: Sequence[artifacts.InputRef],
    refusal_code: DerivationRefusalCode,
) -> None:
    if (
        projection.kind != kind
        or projection.media_type != "application/json"
        or (projection.schema_name, projection.schema_version) != (schema.name, schema.version)
        or (projection.producer_component, projection.producer_version)
        != _producer_projection(producer)
        or projection.input_graph != _expected_input_edges(inputs)
    ):
        raise DerivationRefusalError(
            refusal_code,
            f"{projection.artifact_id}: manifest contract",
        )


def _load_source(
    store: artifacts.FileSystemCAS,
    projection: ArtifactContractProjection,
    *,
    refusal_code: DerivationRefusalCode,
) -> SourceSeries:
    current = _manifest_projection(store, projection.artifact_id)
    if current != projection:
        raise DerivationRefusalError(
            refusal_code,
            f"{projection.artifact_id}: complete manifest projection",
        )
    try:
        payload = canon.from_canonical_bytes(store.get_bytes(projection.artifact_id))
        source = SourceSeries.model_validate(payload)
    except (OSError, ValueError) as exc:
        raise DerivationRefusalError(refusal_code, str(projection.artifact_id)) from exc
    _require_registered_basis_units((source.basis,))
    expected_inputs = _authority_input_refs(source.authority)
    _verify_intake_contract(
        projection,
        kind=SOURCE_SERIES_KIND,
        schema=_SOURCE_SERIES_SCHEMA,
        producer=_SOURCE_SERIES_PRODUCER,
        inputs=expected_inputs,
        refusal_code=refusal_code,
    )
    for item in expected_inputs:
        try:
            _verify_resolvable_ref(store, item.artifact_id)
        except DerivationRefusalError as exc:
            raise DerivationRefusalError(
                refusal_code,
                f"{projection.artifact_id}: unresolved input {item.role}={item.artifact_id}",
            ) from exc
    return source


def _registry_bases(
    registry: TransformFamilyRegistry,
) -> Iterable[BasisSignature]:
    for family in registry.families:
        yield from (item.basis for item in family.input_specs)
        yield family.output_basis


def persist_transform_family_registry(
    store: artifacts.FileSystemCAS,
    registry: TransformFamilyRegistry,
) -> artifacts.ArtifactRef:
    """Persist one unit-resolved owner registry under the canonical CAS contract."""

    try:
        registry = TransformFamilyRegistry.model_validate(registry.model_dump(mode="python"))
    except ValueError as exc:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            "transform family registry identity or content drift",
        ) from exc
    _require_registered_basis_units(_registry_bases(registry))
    ref, _ = _put_or_verify(
        store,
        payload=registry,
        kind=TRANSFORM_FAMILY_REGISTRY_KIND,
        schema=_TRANSFORM_FAMILY_REGISTRY_SCHEMA,
        inputs=(),
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    return ref


def _load_transform_family_registry_artifact(
    store: artifacts.FileSystemCAS,
    projection: ArtifactContractProjection,
    *,
    refusal_code: DerivationRefusalCode,
) -> TransformFamilyRegistry:
    current = _manifest_projection(store, projection.artifact_id)
    if current != projection:
        raise DerivationRefusalError(
            refusal_code,
            f"{projection.artifact_id}: complete manifest projection",
        )
    _verify_intake_contract(
        projection,
        kind=TRANSFORM_FAMILY_REGISTRY_KIND,
        schema=_TRANSFORM_FAMILY_REGISTRY_SCHEMA,
        producer=_DERIVATION_PRODUCER,
        inputs=(),
        refusal_code=refusal_code,
    )
    try:
        payload = canon.from_canonical_bytes(store.get_bytes(projection.artifact_id))
        registry = TransformFamilyRegistry.model_validate(payload)
    except (OSError, ValueError) as exc:
        raise DerivationRefusalError(refusal_code, str(projection.artifact_id)) from exc
    _require_registered_basis_units(_registry_bases(registry))
    return registry


def _derive_parameters(
    family: TransformFamily,
    sources: Mapping[str, SourceSeries],
) -> tuple[DerivedParameter, ...]:
    parameters: list[DerivedParameter] = []
    for rule in family.parameter_rules:
        if rule.operator == "literal":
            if rule.literal_value is None:
                raise DerivationRefusalError(
                    DerivationRefusalCode.PARAMETER_DERIVATION_FAILED,
                    f"{rule.name}: literal value missing",
                )
            value = rule.literal_value
        else:
            common_years = {point.year for point in sources[rule.input_roles[0]].points}
            for role in rule.input_roles[1:]:
                common_years.intersection_update(point.year for point in sources[role].points)
            if not common_years:
                raise DerivationRefusalError(
                    DerivationRefusalCode.PARAMETER_DERIVATION_FAILED,
                    f"{rule.name}: no common year",
                )
            years = sorted(common_years)
            value = Decimal(years[(len(years) - 1) // 2])
        parameters.append(DerivedParameter(name=rule.name, rule=rule, value=value))
    return tuple(parameters)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _resolve_assumptions(
    family: TransformFamily,
    parameters: Sequence[DerivedParameter],
) -> tuple[ResolvedAssumption, ...]:
    values = {item.name: item.value for item in parameters}
    return tuple(
        ResolvedAssumption(
            name=rule.name,
            value=(
                rule.literal_value
                if rule.literal_value is not None
                else _decimal_text(values[rule.parameter_name or ""])
            ),
        )
        for rule in family.assumption_rules
    )


def _validate_output_parameter_bindings(
    family: TransformFamily,
    parameters: Sequence[DerivedParameter],
    output_basis: BasisSignature,
) -> None:
    values = {item.name: _decimal_text(item.value) for item in parameters}
    for binding in family.output_parameter_bindings:
        if output_basis.attribute(binding.output_attribute) != values[binding.parameter_name]:
            raise ValueError(
                f"output basis {binding.output_attribute} differs from "
                f"parameter {binding.parameter_name}"
            )


def _materialize_output_basis(
    family: TransformFamily,
    parameters: Sequence[DerivedParameter],
) -> BasisSignature:
    """Resolve only parameter-bound output attributes from family-owned rules."""

    parameter_values = {item.name: _decimal_text(item.value) for item in parameters}
    bindings = {
        item.output_attribute: item.parameter_name for item in family.output_parameter_bindings
    }
    return BasisSignature(
        quantity_kind=family.output_basis.quantity_kind,
        unit=family.output_basis.unit,
        attributes=tuple(
            BasisAttribute(
                name=attribute.name,
                value=(
                    parameter_values[bindings[attribute.name]]
                    if attribute.name in bindings
                    else attribute.value
                ),
            )
            for attribute in family.output_basis.attributes
        ),
    )


def build_derivation_recipe(
    store: artifacts.FileSystemCAS,
    *,
    registry: TransformFamilyRegistry,
    input_refs: Mapping[str, artifacts.ArtifactRef],
    output_variable_id: str,
    output_basis: BasisSignature | None = None,
    family_id: str | None = None,
    method_version: str | None = None,
) -> DerivationRecipe:
    """Resolve owner family data and bind exact inputs into a canonical recipe."""

    registry_ref = persist_transform_family_registry(store, registry)
    registry_projection = _manifest_projection(store, registry_ref.artifact_id)
    _load_transform_family_registry_artifact(
        store,
        registry_projection,
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    sources: dict[str, SourceSeries] = {}
    projections: dict[str, ArtifactContractProjection] = {}
    for role, ref in sorted(input_refs.items()):
        if ref.kind != SOURCE_SERIES_KIND:
            raise DerivationRefusalError(
                DerivationRefusalCode.BASIS_MISMATCH,
                f"{role}: input does not carry the source-series kind",
                reason=DerivationRefusalReason.NO_CERTIFIED_TRANSFORM,
            )
        projection = _manifest_projection(store, ref.artifact_id)
        projections[role] = projection
        sources[role] = _load_source(
            store,
            projection,
            refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
        )
    input_bases = {role: source.basis for role, source in sources.items()}
    if output_basis is None:
        family = registry.resolve_for_inputs(
            input_bases=input_bases,
            family_id=family_id,
            method_version=method_version,
        )
    else:
        family = registry.resolve(
            input_bases=input_bases,
            output_basis=output_basis,
            family_id=family_id,
            method_version=method_version,
        )
    parameters = _derive_parameters(family, sources)
    resolved_output_basis = (
        _materialize_output_basis(family, parameters) if output_basis is None else output_basis
    )
    try:
        _validate_output_parameter_bindings(family, parameters, resolved_output_basis)
    except ValueError as exc:
        raise DerivationRefusalError(
            DerivationRefusalCode.BASIS_MISMATCH,
            str(exc),
            reason=DerivationRefusalReason.NO_CERTIFIED_TRANSFORM,
        ) from exc
    payload: dict[str, object] = {
        "schema_version": DERIVATION_SCHEMA_VERSION,
        "registry_artifact": registry_projection,
        "family": family,
        "method_id": family.method_id,
        "method_version": family.method_version,
        "inputs": tuple(
            RecipeInput(role=role, artifact=projections[role], basis=sources[role].basis)
            for role in sorted(sources)
        ),
        "output_variable_id": output_variable_id,
        "output_basis": resolved_output_basis,
        "parameters": parameters,
        "assumptions": _resolve_assumptions(family, parameters),
    }
    payload["recipe_id"] = _identity("derivation-recipe", payload)
    return DerivationRecipe.model_validate(payload)


def _check_constraints(spec: TransformInputSpec, source: SourceSeries) -> None:
    for constraint in spec.value_constraints:
        for point in source.points:
            valid = {
                "nonnegative": point.value >= 0,
                "nonzero": point.value != 0,
                "positive": point.value > 0,
            }[constraint]
            if not valid:
                raise DerivationRefusalError(
                    DerivationRefusalCode.INPUT_VALUE_CONSTRAINT,
                    f"{spec.role}/{constraint}/{point.year}",
                )


def _integer_parameter(
    parameters: Mapping[str, Decimal],
    name: str,
) -> int:
    value = parameters[name]
    if value != value.to_integral_value():
        raise DerivationRefusalError(
            DerivationRefusalCode.PARAMETER_DERIVATION_FAILED,
            f"{name}: expected an integer year",
        )
    return int(value)


def _evaluate_expression(
    expression: ArithmeticExpression,
    *,
    year: int,
    values_by_role: Mapping[str, Mapping[int, Decimal]],
    parameters: Mapping[str, Decimal],
) -> Decimal:
    if expression.operator == "current_value":
        if expression.role is None:
            raise DerivationRefusalError(
                DerivationRefusalCode.ARITHMETIC_DOMAIN_ERROR,
                "current_value role missing",
            )
        return values_by_role[expression.role][year]
    if expression.operator == "value_at_parameter":
        if expression.role is None or expression.parameter_name is None:
            raise DerivationRefusalError(
                DerivationRefusalCode.ARITHMETIC_DOMAIN_ERROR,
                "value_at_parameter address missing",
            )
        parameter_year = _integer_parameter(parameters, expression.parameter_name)
        try:
            return values_by_role[expression.role][parameter_year]
        except KeyError as exc:
            raise DerivationRefusalError(
                DerivationRefusalCode.PARAMETER_DERIVATION_FAILED,
                f"{expression.role}: year {parameter_year} missing",
            ) from exc
    if expression.operator == "parameter":
        if expression.parameter_name is None:
            raise DerivationRefusalError(
                DerivationRefusalCode.ARITHMETIC_DOMAIN_ERROR,
                "parameter name missing",
            )
        return parameters[expression.parameter_name]
    if expression.operator == "constant":
        if expression.constant_value is None:
            raise DerivationRefusalError(
                DerivationRefusalCode.ARITHMETIC_DOMAIN_ERROR,
                "constant value missing",
            )
        return expression.constant_value
    left = _evaluate_expression(
        expression.operands[0],
        year=year,
        values_by_role=values_by_role,
        parameters=parameters,
    )
    right = _evaluate_expression(
        expression.operands[1],
        year=year,
        values_by_role=values_by_role,
        parameters=parameters,
    )
    try:
        if expression.operator == "add":
            return left + right
        if expression.operator == "subtract":
            return left - right
        if expression.operator == "multiply":
            return left * right
        return left / right
    except (DivisionByZero, InvalidOperation, ZeroDivisionError) as exc:
        raise DerivationRefusalError(
            DerivationRefusalCode.ARITHMETIC_DOMAIN_ERROR,
            f"{expression.operator}/{year}",
        ) from exc


def _load_recipe_sources(
    store: artifacts.FileSystemCAS,
    recipe: DerivationRecipe,
    *,
    refusal_code: DerivationRefusalCode,
) -> dict[str, SourceSeries]:
    sources = {
        item.role: _load_source(store, item.artifact, refusal_code=refusal_code)
        for item in recipe.inputs
    }
    spec_by_role = {item.role: item for item in recipe.family.input_specs}
    if any(source.basis != spec_by_role[role].basis for role, source in sources.items()):
        raise DerivationRefusalError(
            DerivationRefusalCode.BASIS_MISMATCH,
            "input basis differs from the certified recipe",
        )
    actual_parameters = _derive_parameters(recipe.family, sources)
    if actual_parameters != recipe.parameters:
        raise DerivationRefusalError(
            refusal_code,
            "derived parameters differ from the certified recipe",
        )
    return sources


def _resolve_recipe_family(
    store: artifacts.FileSystemCAS,
    recipe: DerivationRecipe,
    *,
    refusal_code: DerivationRefusalCode,
) -> TransformFamily:
    registry = _load_transform_family_registry_artifact(
        store,
        recipe.registry_artifact,
        refusal_code=refusal_code,
    )
    family = registry.resolve(
        input_bases={item.role: item.basis for item in recipe.inputs},
        output_basis=recipe.output_basis,
        family_id=recipe.family.family_id,
        method_version=recipe.family.method_version,
    )
    if family != recipe.family:
        raise DerivationRefusalError(
            DerivationRefusalCode.BASIS_MISMATCH,
            f"{recipe.family.family_id}: embedded family differs from owner registry",
            reason=DerivationRefusalReason.NO_CERTIFIED_TRANSFORM,
        )
    return family


def _revalidate_recipe(
    recipe: DerivationRecipe,
    *,
    refusal_code: DerivationRefusalCode,
) -> DerivationRecipe:
    try:
        return DerivationRecipe.model_validate(recipe.model_dump(mode="python"))
    except ValueError as exc:
        raise DerivationRefusalError(
            refusal_code,
            "derivation recipe identity or content drift",
        ) from exc


def _derive_series(
    recipe: DerivationRecipe,
    sources: Mapping[str, SourceSeries],
) -> DerivedSeries:
    spec_by_role = {item.role: item for item in recipe.family.input_specs}
    for role, source in sources.items():
        _check_constraints(spec_by_role[role], source)
    values_by_role = {
        role: {point.year: point.value for point in source.points}
        for role, source in sources.items()
    }
    domain_years = tuple(values_by_role[recipe.family.year_domain_role])
    for role, values in values_by_role.items():
        missing = tuple(year for year in domain_years if year not in values)
        if missing:
            raise DerivationRefusalError(
                DerivationRefusalCode.EXACT_YEAR_MISSING,
                f"{role}:" + ",".join(str(year) for year in missing),
            )
    parameters = {item.name: item.value for item in recipe.parameters}
    with localcontext() as context:
        context.prec = 50
        points = tuple(
            SeriesPoint(
                year=year,
                value=_evaluate_expression(
                    recipe.family.expression,
                    year=year,
                    values_by_role=values_by_role,
                    parameters=parameters,
                ),
            )
            for year in domain_years
        )
    return DerivedSeries(
        variable_id=recipe.output_variable_id,
        basis=recipe.output_basis,
        points=points,
        recipe_id=recipe.recipe_id,
        source_artifact_ids=tuple(
            {str(item.artifact.artifact_id): item.artifact.artifact_id for item in recipe.inputs}[
                artifact_id
            ]
            for artifact_id in sorted({str(item.artifact.artifact_id) for item in recipe.inputs})
        ),
        observation_class="derived",
    )


def _expected_output_inputs(recipe: DerivationRecipe) -> list[artifacts.InputRef]:
    return _sorted_input_refs(
        [
            artifacts.InputRef(
                artifact_id=recipe.registry_artifact.artifact_id,
                role="transform_family_registry",
            ),
            *(
                artifacts.InputRef(
                    artifact_id=item.artifact.artifact_id,
                    role=f"source:{item.role}",
                )
                for item in recipe.inputs
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
            raise DerivationRefusalError(refusal_code, "CAS returned a different identity")
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
    sources: Mapping[str, SourceSeries],
    derived_artifact_id: artifacts.ArtifactID,
) -> DerivationCertificate:
    artifact_by_role = {item.role: item.artifact.artifact_id for item in recipe.inputs}
    authority_by_artifact = {
        str(artifact_by_role[role]): CertificateInputAuthority(
            artifact_id=artifact_by_role[role],
            effective_score=source.authority.effective_score,
            authority_ref=source.authority.authority_ref,
            verifier_provenance_ref=source.authority.verifier_provenance_ref,
        )
        for role, source in sources.items()
    }
    authorities = tuple(
        sorted(authority_by_artifact.values(), key=lambda item: str(item.artifact_id))
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


def materialize_derivation(
    store: artifacts.FileSystemCAS,
    recipe: DerivationRecipe,
) -> DerivationMaterialization:
    """Produce or verify one family-defined derivation and its certificate."""

    recipe = _revalidate_recipe(
        recipe,
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    _resolve_recipe_family(
        store,
        recipe,
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    sources = _load_recipe_sources(
        store,
        recipe,
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    series = _derive_series(recipe, sources)
    derived_ref, cache_hit = _put_or_verify(
        store,
        payload=series,
        kind=DERIVED_SERIES_KIND,
        schema=_DERIVED_SERIES_SCHEMA,
        inputs=_expected_output_inputs(recipe),
        refusal_code=DerivationRefusalCode.CACHE_ARTIFACT_DRIFT,
    )
    certificate = _certificate(recipe, sources, derived_ref.artifact_id)
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
    """Recompute a certificate graph before exposing values to one consumer."""

    if not consumer_method_id.strip():
        raise ValueError("consumer_method_id must be non-empty")
    if certificate_ref.kind != DERIVATION_CERTIFICATE_KIND:
        raise DerivationRefusalError(
            DerivationRefusalCode.CERTIFICATE_DRIFT,
            "certificate ref carries the wrong artifact kind",
        )
    try:
        payload = canon.from_canonical_bytes(store.get_bytes(certificate_ref.artifact_id))
    except (OSError, ValueError) as exc:
        raise DerivationRefusalError(
            DerivationRefusalCode.CERTIFICATE_DRIFT,
            str(certificate_ref.artifact_id),
        ) from exc
    if (
        isinstance(payload, Mapping)
        and payload.get("schema_version") == LEGACY_DERIVATION_SCHEMA_VERSION
    ):
        _raise_legacy_v1_unsupported(str(certificate_ref.artifact_id))
    try:
        certificate = DerivationCertificate.model_validate(payload)
    except ValueError as exc:
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
    _resolve_recipe_family(
        store,
        certificate.recipe,
        refusal_code=DerivationRefusalCode.CERTIFICATE_DRIFT,
    )
    sources = _load_recipe_sources(
        store,
        certificate.recipe,
        refusal_code=DerivationRefusalCode.CERTIFICATE_DRIFT,
    )
    expected_series = _derive_series(certificate.recipe, sources)
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
    if certificate != _certificate(
        certificate.recipe,
        sources,
        certificate.derived_artifact_id,
    ):
        raise DerivationRefusalError(
            DerivationRefusalCode.CERTIFICATE_DRIFT,
            "certificate differs from recomputed authority and recipe",
        )
    receipt_payload: dict[str, object] = {
        "consumer_method_id": consumer_method_id,
        "certificate_artifact_id": certificate_ref.artifact_id,
        "derived_artifact_id": certificate.derived_artifact_id,
        "series": tuple(point.value for point in expected_series.points),
        "observation_class": "derived",
        "cache_verified": True,
    }
    receipt_payload["consumption_id"] = _identity(
        "derivation-consumption",
        receipt_payload,
    )
    return CertifiedDerivationConsumption.model_validate(receipt_payload)


EconomicBasis = _UnsupportedLegacyV1Contract
EconomicSeries = _UnsupportedLegacyV1Contract
PriceIndexBasis = _UnsupportedLegacyV1Contract
PriceIndexSeries = _UnsupportedLegacyV1Contract
DerivedEconomicSeries = _UnsupportedLegacyV1Contract


def build_cpi_derivation_recipe(*_args: object, **_kwargs: object) -> Never:
    """Typed-refuse the removed CPI-specific v1 recipe builder."""

    _raise_legacy_v1_unsupported("build_cpi_derivation_recipe")


def materialize_cpi_real_terms(*_args: object, **_kwargs: object) -> Never:
    """Typed-refuse the removed CPI-specific v1 materializer."""

    _raise_legacy_v1_unsupported("materialize_cpi_real_terms")


def persist_economic_series(*_args: object, **_kwargs: object) -> Never:
    """Typed-refuse persistence through the caller-produced v1 source contract."""

    _raise_legacy_v1_unsupported("persist_economic_series")


def persist_price_index_series(*_args: object, **_kwargs: object) -> Never:
    """Typed-refuse persistence through the caller-produced v1 index contract."""

    _raise_legacy_v1_unsupported("persist_price_index_series")


__all__ = [
    "DERIVATION_CERTIFICATE_KIND",
    "DERIVATION_SCHEMA_VERSION",
    "DERIVED_SERIES_KIND",
    "ECONOMIC_SERIES_KIND",
    "LEGACY_DERIVATION_SCHEMA_VERSION",
    "PRICE_INDEX_SERIES_KIND",
    "SOURCE_SERIES_KIND",
    "TRANSFORM_FAMILY_REGISTRY_KIND",
    "ArithmeticExpression",
    "ArtifactContractProjection",
    "ArtifactInputEdge",
    "AssumptionRule",
    "AuthorityProjection",
    "BasisAttribute",
    "BasisParameterBinding",
    "BasisSignature",
    "CertificateInputAuthority",
    "CertifiedDerivationConsumption",
    "DerivationCertificate",
    "DerivationMaterialization",
    "DerivationRecipe",
    "DerivationRefusalCode",
    "DerivationRefusalError",
    "DerivationRefusalReason",
    "DerivedEconomicSeries",
    "DerivedParameter",
    "DerivedSeries",
    "EconomicBasis",
    "EconomicSeries",
    "ParameterRule",
    "PriceIndexBasis",
    "PriceIndexSeries",
    "RecipeInput",
    "ResolvedAssumption",
    "SeriesPoint",
    "SourceSeries",
    "TransformFamily",
    "TransformFamilyRegistry",
    "TransformInputSpec",
    "build_cpi_derivation_recipe",
    "build_derivation_recipe",
    "consume_certified_derivation",
    "load_transform_family_registry",
    "materialize_cpi_real_terms",
    "materialize_derivation",
    "persist_economic_series",
    "persist_price_index_series",
    "persist_source_series",
    "persist_transform_family_registry",
]
