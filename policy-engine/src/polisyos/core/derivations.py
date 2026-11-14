"""Canonical certified derivation contracts, arithmetic, and replay.

Existing runtime artifact identities and producer profiles remain unchanged.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, Never, Protocol, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core import artifacts, canon
from polisyos.core.artifacts.protocol import ProfileAddressedManifestStore
from polisyos.ir import api as ir_api

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.ir.kernel import UnitsRegistry


DERIVATION_SCHEMA_VERSION = "polisyos.runtime.derived_observations.v2"


SELECTED_VIEW_DERIVATION_SCHEMA_VERSION = "polisyos.runtime.derived_observations.v2.1"


LEGACY_DERIVATION_SCHEMA_VERSION = "polisyos.runtime.derived_observations.v1"


SOURCE_SERIES_KIND = "polisyos.runtime.derivation_source_series"


ECONOMIC_SERIES_KIND = "polisyos.runtime.economic_series"


PRICE_INDEX_SERIES_KIND = "polisyos.runtime.price_index_series"


TRANSFORM_FAMILY_REGISTRY_KIND = "polisyos.runtime.transform_family_registry"


DERIVED_SERIES_KIND = "polisyos.runtime.derived_economic_series"


DERIVATION_CERTIFICATE_KIND = "polisyos.runtime.derivation_certificate"


DERIVATION_RECIPE_KIND = "polisyos.runtime.derivation_recipe"


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


_DERIVED_SERIES_SELECTED_VIEW_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.derived-economic-series",
    version="2.1.0",
)


_CERTIFICATE_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.derivation-certificate",
    version="2.0.0",
)


_CERTIFICATE_SELECTED_VIEW_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.derivation-certificate",
    version="2.1.0",
)


_DERIVATION_RECIPE_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.derivation-recipe",
    version="2.0.0",
)


_DERIVATION_RECIPE_SELECTED_VIEW_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.derivation-recipe",
    version="2.1.0",
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


class _CertifiedDerivationReader(
    artifacts.ArtifactReader,
    artifacts.RawManifestBytesReader,
    ProfileAddressedManifestStore,
    Protocol,
):
    """Read-only store capabilities required to admit and replay a certificate."""

    def verify(
        self,
        artifact_id: artifacts.ArtifactID | artifacts.ArtifactRef,
    ) -> artifacts.VerificationReport: ...


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
    EPOCH_RECOMPUTE_DRIFT = "epoch_recompute_drift"
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
    allowed_input_kinds: tuple[Literal["source", "candidate_source", "certified_derived"], ...] = (
        Field(
            default=("source",),
            exclude_if=lambda value: value == ("source",),
            min_length=1,
        )
    )

    @model_validator(mode="after")
    def _constraints_are_canonical(self) -> Self:
        if self.allowed_input_kinds != tuple(sorted(set(self.allowed_input_kinds))):
            raise ValueError("allowed input kinds must be unique and sorted")
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
        input_kinds: Mapping[str, str] | None = None,
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
            and (
                input_kinds is None
                or all(
                    input_kinds.get(item.role) in item.allowed_input_kinds
                    for item in family.input_specs
                )
            )
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
        input_kinds: Mapping[str, str] | None = None,
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
            and (
                input_kinds is None
                or all(
                    input_kinds.get(item.role) in item.allowed_input_kinds
                    for item in family.input_specs
                )
            )
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
    *,
    store: _CertifiedDerivationReader | None = None,
    registry_bundle_ref: artifacts.ArtifactRef | None = None,
) -> TransformFamilyRegistry:
    """Load a strict registry from TOML or an already-decoded owner mapping."""

    payload: Mapping[str, object]
    if isinstance(source, Mapping):
        payload = source
    else:
        payload = tomllib.loads(Path(source).read_text(encoding="utf-8"))
    registry = TransformFamilyRegistry.model_validate(payload)
    if registry_bundle_ref is None:
        _require_registered_basis_units(_registry_bases(registry))
    elif store is None:
        raise ValueError("selected model units require their artifact reader")
    else:
        _require_composition_units(store, registry_bundle_ref, _registry_bases(registry))
    return registry


class ArtifactInputEdge(_StrictModel):
    """One exact selected-view direct-input edge in a CAS manifest."""

    role: str = Field(min_length=1)
    artifact_id: artifacts.ArtifactID
    manifest_profile_sha256: str | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )


class ArtifactContractProjection(_StrictModel):
    """Contract fields plus a hash binding the stable manifest projection.

    ``ArtifactManifest.created_at`` is operational evidence and is deliberately
    excluded from recipe identity.  A cold rebuild of identical source bytes
    must therefore produce the same recipe even when its CAS sidecar is written
    at a different wall-clock instant.
    """

    artifact_id: artifacts.ArtifactID
    manifest_profile_sha256: str | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
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
        keys = tuple(
            (edge.role, str(edge.artifact_id), edge.manifest_profile_sha256 or "")
            for edge in self.input_graph
        )
        if keys != tuple(sorted(set(keys))):
            raise ValueError("artifact selected-view input graph must be unique and sorted")
        return self


class RecipeInput(_StrictModel):
    """One role-bound input basis and complete CAS contract projection."""

    role: str = Field(min_length=1)
    artifact: ArtifactContractProjection
    basis: BasisSignature


class DerivationRecipe(_StrictModel):
    """Canonical recipe binding family data, parameters, and every input."""

    schema_version: Literal[
        DERIVATION_SCHEMA_VERSION,
        SELECTED_VIEW_DERIVATION_SCHEMA_VERSION,
    ] = DERIVATION_SCHEMA_VERSION
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
        selected_view = self.registry_artifact.manifest_profile_sha256 is not None or any(
            item.artifact.manifest_profile_sha256 is not None for item in self.inputs
        )
        expected_schema_version = (
            SELECTED_VIEW_DERIVATION_SCHEMA_VERSION if selected_view else DERIVATION_SCHEMA_VERSION
        )
        if self.schema_version != expected_schema_version:
            raise ValueError("recipe wire version differs from selected-view presence")
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

    schema_version: Literal[
        DERIVATION_SCHEMA_VERSION,
        SELECTED_VIEW_DERIVATION_SCHEMA_VERSION,
    ] = DERIVATION_SCHEMA_VERSION
    certificate_id: str = Field(pattern=r"^derivation-certificate:sha256:[0-9a-f]{64}$")
    recipe: DerivationRecipe
    derived_artifact_id: artifacts.ArtifactID
    derived_artifact_ref: artifacts.ArtifactRef | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
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
        selected_view = _recipe_uses_selected_views(self.recipe) or (
            self.derived_artifact_ref is not None
            and self.derived_artifact_ref.manifest_profile_sha256 is not None
        )
        expected_schema_version = (
            SELECTED_VIEW_DERIVATION_SCHEMA_VERSION if selected_view else DERIVATION_SCHEMA_VERSION
        )
        if self.schema_version != expected_schema_version:
            raise ValueError("certificate wire version differs from selected-view presence")
        if self.derived_artifact_ref is not None and (
            self.derived_artifact_ref.artifact_id != self.derived_artifact_id
            or self.derived_artifact_ref.kind != DERIVED_SERIES_KIND
            or self.derived_artifact_ref.media_type != "application/json"
        ):
            raise ValueError("derived artifact reference differs from its certified output")
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


class CertifiedDerivationResolution(_StrictModel):
    """Values reopened by one certificate replay, without a new authority claim."""

    certificate: DerivationCertificate
    series: DerivedSeries
    consumption: CertifiedDerivationConsumption


def _recipe_uses_selected_views(recipe: DerivationRecipe) -> bool:
    return recipe.registry_artifact.manifest_profile_sha256 is not None or any(
        item.artifact.manifest_profile_sha256 is not None for item in recipe.inputs
    )


def _certificate_uses_selected_views(certificate: DerivationCertificate) -> bool:
    return _recipe_uses_selected_views(certificate.recipe) or (
        certificate.derived_artifact_ref is not None
        and certificate.derived_artifact_ref.manifest_profile_sha256 is not None
    )


def _schema_for_input_refs(
    inputs: Sequence[artifacts.InputRef],
    *,
    default: artifacts.SchemaInfo,
    selected_view: artifacts.SchemaInfo,
) -> artifacts.SchemaInfo:
    return (
        selected_view
        if any(item.manifest_profile_sha256 is not None for item in inputs)
        else default
    )


def _recipe_artifact_schema(recipe: DerivationRecipe) -> artifacts.SchemaInfo:
    return (
        _DERIVATION_RECIPE_SELECTED_VIEW_SCHEMA
        if _recipe_uses_selected_views(recipe)
        else _DERIVATION_RECIPE_SCHEMA
    )


def _certificate_artifact_schema(
    certificate: DerivationCertificate,
) -> artifacts.SchemaInfo:
    return (
        _CERTIFICATE_SELECTED_VIEW_SCHEMA
        if _certificate_uses_selected_views(certificate)
        else _CERTIFICATE_SCHEMA
    )


def _identity(prefix: str, payload: object) -> str:
    return f"{prefix}:{canon.fingerprint(payload, prefix=True, canon_spec=_CANON_SPEC)}"


def _canonical_bytes(payload: object) -> bytes:
    return canon.to_canonical_bytes(payload, _CANON_SPEC)


def _canonical_payload(
    raw: bytes, *, store: artifacts.FileSystemCAS, selector: artifacts.ArtifactRef
) -> dict[str, object]:
    try:
        value = artifacts.load_core_json_artifact(store, selector, raw_payload_bytes=raw)
    except CanonicalProfileRefusalError as exc:
        raise ValueError("canonical artifact profile is unavailable") from exc
    if not isinstance(value, Mapping):
        raise ValueError("canonical artifact payload is not a mapping")
    return dict(value)


def _sorted_input_refs(refs: Sequence[artifacts.InputRef]) -> list[artifacts.InputRef]:
    return sorted(
        refs,
        key=lambda item: (
            item.role,
            str(item.artifact_id),
            item.manifest_profile_sha256 or "",
        ),
    )


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
    store: _CertifiedDerivationReader,
    artifact_ref: artifacts.ArtifactID | artifacts.ArtifactRef,
    *,
    refusal_code: DerivationRefusalCode = DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
) -> None:
    try:
        resolved = store.has(artifact_ref) and store.verify(artifact_ref).ok
    except OSError, ValueError, artifacts.ArtifactOwnershipError:
        resolved = False
    if not resolved:
        artifact_id = (
            artifact_ref.artifact_id
            if isinstance(artifact_ref, artifacts.ArtifactRef)
            else artifact_ref
        )
        raise DerivationRefusalError(refusal_code, str(artifact_id))


def _resolve_input_ref(
    store: _CertifiedDerivationReader,
    input_ref: artifacts.InputRef,
    *,
    refusal_code: DerivationRefusalCode,
) -> artifacts.ArtifactRef:
    """Resolve a lineage edge through its exact default or selected sidecar."""

    try:
        if input_ref.manifest_profile_sha256 is None:
            manifest = store.get_manifest(input_ref.artifact_id)
        else:
            manifest = store.get_manifest_by_profile(
                input_ref.artifact_id,
                input_ref.manifest_profile_sha256,
            )
        artifact_ref = artifacts.ArtifactRef(
            artifact_id=input_ref.artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
            manifest_profile_sha256=input_ref.manifest_profile_sha256,
        )
        _verify_resolvable_ref(store, artifact_ref, refusal_code=refusal_code)
        return artifact_ref
    except DerivationRefusalError:
        raise
    except (OSError, ValueError, artifacts.ArtifactOwnershipError) as exc:
        raise DerivationRefusalError(refusal_code, str(input_ref.artifact_id)) from exc


def _verify_input_refs(
    store: _CertifiedDerivationReader,
    input_refs: Sequence[artifacts.InputRef],
    *,
    refusal_code: DerivationRefusalCode,
) -> None:
    for input_ref in _sorted_input_refs(input_refs):
        _resolve_input_ref(store, input_ref, refusal_code=refusal_code)


def _projection_ref(projection: ArtifactContractProjection) -> artifacts.ArtifactRef:
    """Reconstruct the exact typed CAS selector bound by one projection."""

    return artifacts.ArtifactRef(
        artifact_id=projection.artifact_id,
        kind=projection.kind,
        media_type=projection.media_type,
        manifest_profile_sha256=projection.manifest_profile_sha256,
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
    *,
    return_selected_profile: bool = False,
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
        return_selected_profile=return_selected_profile,
    )


def _manifest_sha256(manifest: artifacts.ArtifactManifest) -> str:
    """Hash every manifest field except the operational creation timestamp."""

    return canon.fingerprint(
        manifest.model_dump(mode="json", by_alias=True, exclude={"created_at"}),
        prefix=True,
        canon_spec=_CANON_SPEC,
    )


def _manifest_projection(
    store: _CertifiedDerivationReader,
    artifact_selector: artifacts.ArtifactID | artifacts.ArtifactRef,
) -> ArtifactContractProjection:
    artifact_id = (
        artifact_selector.artifact_id
        if isinstance(artifact_selector, artifacts.ArtifactRef)
        else artifact_selector
    )
    _verify_resolvable_ref(store, artifact_selector)
    try:
        manifest = store.get_manifest(artifact_selector)
    except (OSError, ValueError, artifacts.ArtifactOwnershipError) as exc:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            str(artifact_id),
        ) from exc
    selected_ref = (
        artifact_selector
        if isinstance(artifact_selector, artifacts.ArtifactRef)
        else artifacts.ArtifactRef(
            artifact_id=artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
        )
    )
    _verify_input_refs(
        store,
        manifest.inputs,
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    if manifest.artifact_schema is None or manifest.producer is None:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            f"{artifact_id}: schema/producer missing",
        )
    return ArtifactContractProjection(
        artifact_id=artifact_id,
        manifest_profile_sha256=selected_ref.manifest_profile_sha256,
        kind=manifest.kind,
        media_type=manifest.media_type,
        schema_name=manifest.artifact_schema.name,
        schema_version=manifest.artifact_schema.version,
        producer_component=str(manifest.producer.component),
        producer_version=manifest.producer.version,
        input_graph=tuple(
            ArtifactInputEdge(
                role=item.role,
                artifact_id=item.artifact_id,
                manifest_profile_sha256=item.manifest_profile_sha256,
            )
            for item in _sorted_input_refs(manifest.inputs)
        ),
        manifest_sha256=_manifest_sha256(manifest),
    )


def _expected_input_edges(
    refs: Sequence[artifacts.InputRef],
) -> tuple[ArtifactInputEdge, ...]:
    return tuple(
        ArtifactInputEdge(
            role=item.role,
            artifact_id=item.artifact_id,
            manifest_profile_sha256=item.manifest_profile_sha256,
        )
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
    store: _CertifiedDerivationReader,
    projection: ArtifactContractProjection,
    *,
    refusal_code: DerivationRefusalCode,
) -> SourceSeries:
    from polisyos.core.artifacts import load_core_json_artifact

    current = _manifest_projection(store, _projection_ref(projection))
    if current != projection:
        raise DerivationRefusalError(
            refusal_code,
            f"{projection.artifact_id}: complete manifest projection",
        )
    try:
        payload = load_core_json_artifact(store, _projection_ref(projection))
        source = SourceSeries.model_validate(payload)
    except (OSError, ValueError, artifacts.ArtifactOwnershipError) as exc:
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


def _registry_uses_composition(registry: TransformFamilyRegistry) -> bool:
    return any(
        spec.allowed_input_kinds != ("source",)
        for family in registry.families
        for spec in family.input_specs
    )


def _registry_schema(
    registry: TransformFamilyRegistry, *, selected_units: bool = False
) -> artifacts.SchemaInfo:
    return (
        _TRANSFORM_FAMILY_REGISTRY_V3_SCHEMA
        if _registry_uses_composition(registry) or selected_units
        else _TRANSFORM_FAMILY_REGISTRY_SCHEMA
    )


def _registry_producer(
    registry: TransformFamilyRegistry, *, selected_units: bool = False
) -> artifacts.ProducerInfo:
    return (
        _COMPOSITION_PRODUCER
        if _registry_uses_composition(registry) or selected_units
        else _DERIVATION_PRODUCER
    )


def persist_transform_family_registry(
    store: artifacts.FileSystemCAS,
    registry: TransformFamilyRegistry,
    *,
    registry_bundle_ref: artifacts.ArtifactRef | None = None,
) -> artifacts.ArtifactRef:
    """Persist one unit-resolved owner registry under the canonical CAS contract."""

    try:
        registry = TransformFamilyRegistry.model_validate(registry.model_dump(mode="python"))
    except ValueError as exc:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            "transform family registry identity or content drift",
        ) from exc
    _require_composition_units(store, registry_bundle_ref, _registry_bases(registry))
    ref, _ = _put_or_verify(
        store,
        payload=_CompositionRegistryPayload(registry=registry)
        if _registry_uses_composition(registry) or registry_bundle_ref is not None
        else registry,
        kind=TRANSFORM_FAMILY_REGISTRY_KIND,
        schema=_registry_schema(registry, selected_units=registry_bundle_ref is not None),
        producer=_registry_producer(registry, selected_units=registry_bundle_ref is not None),
        force_selected=_registry_uses_composition(registry) or registry_bundle_ref is not None,
        inputs=()
        if registry_bundle_ref is None
        else _selected_edges([("model_registry_bundle", _require_selected(registry_bundle_ref))]),
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    return ref


def _load_transform_family_registry_artifact(
    store: _CertifiedDerivationReader,
    projection: ArtifactContractProjection,
    *,
    refusal_code: DerivationRefusalCode,
) -> TransformFamilyRegistry:
    from polisyos.core.artifacts import load_core_json_artifact

    current = _manifest_projection(store, _projection_ref(projection))
    if current != projection:
        raise DerivationRefusalError(
            refusal_code,
            f"{projection.artifact_id}: complete manifest projection",
        )
    try:
        payload = load_core_json_artifact(store, _projection_ref(projection))
        registry = (
            _CompositionRegistryPayload.model_validate(payload).registry
            if projection.schema_version == "3.0.0"
            else TransformFamilyRegistry.model_validate(payload)
        )
    except (OSError, ValueError, artifacts.ArtifactOwnershipError) as exc:
        raise DerivationRefusalError(refusal_code, str(projection.artifact_id)) from exc
    unit_edges = [edge for edge in projection.input_graph if edge.role == "model_registry_bundle"]
    if len(unit_edges) > 1 or len(unit_edges) != len(projection.input_graph):
        raise DerivationRefusalError(refusal_code, "registry unit profile input graph differs")
    unit_ref = (
        None
        if not unit_edges
        else _resolve_input_ref(
            store,
            artifacts.InputRef(
                artifact_id=unit_edges[0].artifact_id,
                role="model_registry_bundle",
                manifest_profile_sha256=unit_edges[0].manifest_profile_sha256,
            ),
            refusal_code=refusal_code,
        )
    )
    _verify_intake_contract(
        projection,
        kind=TRANSFORM_FAMILY_REGISTRY_KIND,
        schema=_registry_schema(registry, selected_units=unit_ref is not None),
        producer=_registry_producer(registry, selected_units=unit_ref is not None),
        inputs=() if unit_ref is None else _selected_edges([("model_registry_bundle", unit_ref)]),
        refusal_code=refusal_code,
    )
    _require_composition_units(store, unit_ref, _registry_bases(registry))
    return registry


class _SeriesValues(Protocol):
    @property
    def points(self) -> tuple[SeriesPoint, ...]: ...


def _derive_parameters(
    family: TransformFamily,
    sources: Mapping[str, _SeriesValues],
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
    registry_ref: artifacts.ArtifactRef | None = None,
) -> DerivationRecipe:
    """Resolve owner family data and bind exact inputs into a canonical recipe.

    Args:
        store: Artifact owner used to persist and replay selected inputs.
        registry: Complete transform registry expected by this invocation.
        input_refs: Exact source selections keyed by transform role.
        output_variable_id: Declared identifier of the derived output.
        output_basis: Optional exact output basis used during family resolution.
        family_id: Optional selected family identifier.
        method_version: Optional selected method revision.
        registry_ref: Optional selected view of the already-persisted registry.
            Absence preserves the legacy unselected registry projection.
    """
    if registry_ref is None:
        registry_ref = persist_transform_family_registry(store, registry)
    elif (
        registry_ref.kind != TRANSFORM_FAMILY_REGISTRY_KIND
        or registry_ref.media_type != "application/json"
        or registry_ref.manifest_profile_sha256 is None
    ):
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            "selected transform registry reference required",
        )
    registry_projection = _manifest_projection(store, registry_ref)
    if registry_projection.schema_version == "3.0.0":
        raise DerivationRefusalError(
            DerivationRefusalCode.BASIS_MISMATCH, "v3 registry requires composition entrypoint"
        )
    loaded_registry = _load_transform_family_registry_artifact(
        store,
        registry_projection,
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    if _canonical_bytes(loaded_registry) != _canonical_bytes(registry):
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            "selected transform registry differs from the declared registry",
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
        projection = _manifest_projection(store, ref)
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
    if any(spec.allowed_input_kinds != ("source",) for spec in family.input_specs):
        raise DerivationRefusalError(
            DerivationRefusalCode.BASIS_MISMATCH, "v3 family requires composition entrypoint"
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
    selected_view = registry_projection.manifest_profile_sha256 is not None or any(
        projection.manifest_profile_sha256 is not None for projection in projections.values()
    )
    payload: dict[str, object] = {
        "schema_version": (
            SELECTED_VIEW_DERIVATION_SCHEMA_VERSION if selected_view else DERIVATION_SCHEMA_VERSION
        ),
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


def _check_constraints(spec: TransformInputSpec, source: _SeriesValues) -> None:
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
    store: _CertifiedDerivationReader,
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
    store: _CertifiedDerivationReader,
    recipe: DerivationRecipe,
    *,
    refusal_code: DerivationRefusalCode,
) -> TransformFamily:
    if recipe.registry_artifact.schema_version == "3.0.0":
        raise DerivationRefusalError(
            DerivationRefusalCode.BASIS_MISMATCH, "v3 registry requires composition entrypoint"
        )
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
    if any(spec.allowed_input_kinds != ("source",) for spec in family.input_specs):
        raise DerivationRefusalError(
            DerivationRefusalCode.BASIS_MISMATCH, "v3 family requires composition entrypoint"
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


def _evaluate_points(
    family: TransformFamily,
    parameters: Sequence[DerivedParameter],
    sources: Mapping[str, _SeriesValues],
) -> tuple[SeriesPoint, ...]:
    spec_by_role = {item.role: item for item in family.input_specs}
    for role, source in sources.items():
        _check_constraints(spec_by_role[role], source)
    values_by_role = {
        role: {point.year: point.value for point in source.points}
        for role, source in sources.items()
    }
    domain_years = tuple(values_by_role[family.year_domain_role])
    for role, values in values_by_role.items():
        missing = tuple(year for year in domain_years if year not in values)
        if missing:
            raise DerivationRefusalError(
                DerivationRefusalCode.EXACT_YEAR_MISSING,
                f"{role}:" + ",".join(str(year) for year in missing),
            )
    parameter_values = {item.name: item.value for item in parameters}
    with localcontext() as context:
        context.prec = 50
        points = tuple(
            SeriesPoint(
                year=year,
                value=_evaluate_expression(
                    family.expression,
                    year=year,
                    values_by_role=values_by_role,
                    parameters=parameter_values,
                ),
            )
            for year in domain_years
        )
    return points


def _derive_series(
    recipe: DerivationRecipe,
    sources: Mapping[str, SourceSeries],
) -> DerivedSeries:
    points = _evaluate_points(recipe.family, recipe.parameters, sources)
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
                manifest_profile_sha256=recipe.registry_artifact.manifest_profile_sha256,
            ),
            *(
                artifacts.InputRef(
                    artifact_id=item.artifact.artifact_id,
                    role=f"source:{item.role}",
                    manifest_profile_sha256=item.artifact.manifest_profile_sha256,
                )
                for item in recipe.inputs
            ),
        ]
    )


def _expected_certificate_inputs(
    recipe: DerivationRecipe,
    derived_artifact: artifacts.ArtifactID | artifacts.ArtifactRef,
) -> list[artifacts.InputRef]:
    artifact_id = (
        derived_artifact.artifact_id
        if isinstance(derived_artifact, artifacts.ArtifactRef)
        else derived_artifact
    )
    profile = (
        derived_artifact.manifest_profile_sha256
        if isinstance(derived_artifact, artifacts.ArtifactRef)
        else None
    )
    return _sorted_input_refs(
        [
            *_expected_output_inputs(recipe),
            artifacts.InputRef(
                artifact_id=artifact_id,
                role="derived_series",
                manifest_profile_sha256=profile,
            ),
        ]
    )


def _producer_projection(producer: artifacts.ProducerInfo) -> tuple[str, str]:
    return str(producer.component), producer.version


def _verify_cached_artifact(
    store: _CertifiedDerivationReader,
    *,
    artifact_ref: artifacts.ArtifactRef,
    expected_bytes: bytes,
    kind: str,
    schema: artifacts.SchemaInfo,
    producer: artifacts.ProducerInfo,
    inputs: Sequence[artifacts.InputRef],
    refusal_code: DerivationRefusalCode,
) -> artifacts.ArtifactRef:
    artifact_id = artifact_ref.artifact_id
    try:
        if not store.has(artifact_ref) or not store.verify(artifact_ref).ok:
            raise DerivationRefusalError(refusal_code, f"{artifact_id}: CAS integrity")
        if store.get_bytes(artifact_ref) != expected_bytes:
            raise DerivationRefusalError(refusal_code, f"{artifact_id}: bytes")
        manifest = store.get_manifest(artifact_ref)
    except DerivationRefusalError:
        raise
    except (OSError, ValueError, artifacts.ArtifactOwnershipError) as exc:
        raise DerivationRefusalError(refusal_code, str(artifact_id)) from exc
    if (
        artifact_ref.kind != kind
        or artifact_ref.media_type != "application/json"
        or manifest.kind != kind
        or manifest.media_type != "application/json"
        or manifest.artifact_schema != schema
        or manifest.producer is None
        or _producer_projection(manifest.producer) != _producer_projection(producer)
        or _sorted_input_refs(manifest.inputs) != _sorted_input_refs(inputs)
    ):
        raise DerivationRefusalError(refusal_code, f"{artifact_id}: manifest contract")
    _verify_input_refs(store, inputs, refusal_code=refusal_code)
    return artifact_ref


def _put_or_verify(
    store: artifacts.FileSystemCAS,
    *,
    payload: object,
    kind: str,
    schema: artifacts.SchemaInfo,
    inputs: Sequence[artifacts.InputRef],
    refusal_code: DerivationRefusalCode,
    producer: artifacts.ProducerInfo = _DERIVATION_PRODUCER,
    force_selected: bool = False,
) -> tuple[artifacts.ArtifactRef, bool]:
    data = _canonical_bytes(payload)
    artifact_id = artifacts.ArtifactID.from_sha256_hex(canon.content_hash(data))
    cache_hit = store.has(artifact_id)
    sorted_inputs = _sorted_input_refs(inputs)
    has_selected_input_view = force_selected or any(
        item.manifest_profile_sha256 is not None for item in sorted_inputs
    )
    _verify_input_refs(store, sorted_inputs, refusal_code=refusal_code)
    if cache_hit:
        default_ref = artifacts.ArtifactRef(
            artifact_id=artifact_id,
            kind=kind,
            media_type="application/json",
        )
        if not has_selected_input_view:
            return (
                _verify_cached_artifact(
                    store,
                    artifact_ref=default_ref,
                    expected_bytes=data,
                    kind=kind,
                    schema=schema,
                    producer=producer,
                    inputs=sorted_inputs,
                    refusal_code=refusal_code,
                ),
                True,
            )
        try:
            if not store.verify(artifact_id).ok:
                raise DerivationRefusalError(
                    refusal_code,
                    f"{artifact_id}: CAS integrity",
                )
        except DerivationRefusalError:
            raise
        except (OSError, ValueError, artifacts.ArtifactOwnershipError) as exc:
            raise DerivationRefusalError(
                refusal_code,
                f"{artifact_id}: CAS integrity",
            ) from exc
    try:
        ref = store.put_bytes(
            data,
            artifacts.PutOptions(
                kind=kind,
                media_type="application/json",
                schema=schema,
                producer=producer,
                inputs=sorted_inputs,
                canon=artifacts.CanonInfo.from_spec(_CANON_SPEC),
            ),
            return_selected_profile=has_selected_input_view,
        )
    except artifacts.ArtifactIntegrityError as exc:
        raise DerivationRefusalError(
            refusal_code,
            f"{artifact_id}: CAS integrity",
        ) from exc
    if ref.artifact_id != artifact_id:
        raise DerivationRefusalError(refusal_code, "CAS returned a different identity")
    if has_selected_input_view and ref.manifest_profile_sha256 is None:
        raise DerivationRefusalError(
            refusal_code,
            "CAS omitted selected manifest profile for a selected input view",
        )
    return (
        _verify_cached_artifact(
            store,
            artifact_ref=ref,
            expected_bytes=data,
            kind=kind,
            schema=schema,
            producer=producer,
            inputs=sorted_inputs,
            refusal_code=refusal_code,
        ),
        cache_hit,
    )


def _certificate(
    recipe: DerivationRecipe,
    sources: Mapping[str, SourceSeries],
    derived_artifact: artifacts.ArtifactID | artifacts.ArtifactRef,
) -> DerivationCertificate:
    derived_artifact_ref = (
        derived_artifact if isinstance(derived_artifact, artifacts.ArtifactRef) else None
    )
    derived_artifact_id = (
        derived_artifact.artifact_id
        if isinstance(derived_artifact, artifacts.ArtifactRef)
        else derived_artifact
    )
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
    selected_view = _recipe_uses_selected_views(recipe) or (
        derived_artifact_ref is not None
        and derived_artifact_ref.manifest_profile_sha256 is not None
    )
    payload: dict[str, object] = {
        "schema_version": (
            SELECTED_VIEW_DERIVATION_SCHEMA_VERSION if selected_view else DERIVATION_SCHEMA_VERSION
        ),
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
    if (
        derived_artifact_ref is not None
        and derived_artifact_ref.manifest_profile_sha256 is not None
    ):
        payload["derived_artifact_ref"] = derived_artifact_ref
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
    output_inputs = _expected_output_inputs(recipe)
    derived_ref, cache_hit = _put_or_verify(
        store,
        payload=series,
        kind=DERIVED_SERIES_KIND,
        schema=_schema_for_input_refs(
            output_inputs,
            default=_DERIVED_SERIES_SCHEMA,
            selected_view=_DERIVED_SERIES_SELECTED_VIEW_SCHEMA,
        ),
        inputs=output_inputs,
        refusal_code=DerivationRefusalCode.CACHE_ARTIFACT_DRIFT,
    )
    certificate = _certificate(recipe, sources, derived_ref)
    certificate_ref, _ = _put_or_verify(
        store,
        payload=certificate,
        kind=DERIVATION_CERTIFICATE_KIND,
        schema=_certificate_artifact_schema(certificate),
        inputs=_expected_certificate_inputs(recipe, derived_ref),
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


def resolve_certified_derivation(
    store: _CertifiedDerivationReader,
    *,
    certificate_ref: artifacts.ArtifactRef,
    consumer_method_id: str,
) -> CertifiedDerivationResolution:
    """Recompute a certificate graph and return its exact recipe and series."""
    from polisyos.core.artifacts import load_core_json_artifact

    if not consumer_method_id.strip():
        raise ValueError("consumer_method_id must be non-empty")
    if certificate_ref.kind != DERIVATION_CERTIFICATE_KIND:
        raise DerivationRefusalError(
            DerivationRefusalCode.CERTIFICATE_DRIFT,
            "certificate ref carries the wrong artifact kind",
        )
    try:
        payload = load_core_json_artifact(store, certificate_ref)
    except (OSError, ValueError, artifacts.ArtifactOwnershipError) as exc:
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
        artifact_ref=certificate_ref,
        expected_bytes=_canonical_bytes(certificate),
        kind=DERIVATION_CERTIFICATE_KIND,
        schema=_certificate_artifact_schema(certificate),
        producer=_DERIVATION_PRODUCER,
        inputs=_expected_certificate_inputs(
            certificate.recipe,
            certificate.derived_artifact_ref or certificate.derived_artifact_id,
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
    derived_ref = certificate.derived_artifact_ref or artifacts.ArtifactRef(
        artifact_id=certificate.derived_artifact_id,
        kind=DERIVED_SERIES_KIND,
        media_type="application/json",
    )
    derived_inputs = _expected_output_inputs(certificate.recipe)
    _verify_cached_artifact(
        store,
        artifact_ref=derived_ref,
        expected_bytes=expected_bytes,
        kind=DERIVED_SERIES_KIND,
        schema=_schema_for_input_refs(
            derived_inputs,
            default=_DERIVED_SERIES_SCHEMA,
            selected_view=_DERIVED_SERIES_SELECTED_VIEW_SCHEMA,
        ),
        producer=_DERIVATION_PRODUCER,
        inputs=derived_inputs,
        refusal_code=DerivationRefusalCode.CACHE_ARTIFACT_DRIFT,
    )
    if certificate != _certificate(
        certificate.recipe,
        sources,
        derived_ref,
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
    return CertifiedDerivationResolution(
        certificate=certificate,
        series=expected_series,
        consumption=CertifiedDerivationConsumption.model_validate(receipt_payload),
    )


def consume_certified_derivation(
    store: _CertifiedDerivationReader,
    *,
    certificate_ref: artifacts.ArtifactRef,
    consumer_method_id: str,
) -> CertifiedDerivationConsumption:
    """Recompute a certificate graph before exposing values to one consumer."""
    return resolve_certified_derivation(
        store,
        certificate_ref=certificate_ref,
        consumer_method_id=consumer_method_id,
    ).consumption


def _epoch_recompute_refusal(detail: str) -> DerivationRefusalError:
    return DerivationRefusalError(DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT, detail)


def persist_derivation_recipe_artifact(
    store: artifacts.FileSystemCAS,
    recipe: DerivationRecipe,
) -> artifacts.ArtifactRef:
    """Persist the exact recipe profile consumed by epoch certificate bindings."""

    recipe = _revalidate_recipe(
        recipe,
        refusal_code=DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
    )
    _resolve_recipe_family(
        store,
        recipe,
        refusal_code=DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
    )
    _load_recipe_sources(
        store,
        recipe,
        refusal_code=DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
    )
    ref, _ = _put_or_verify(
        store,
        payload=recipe,
        kind=DERIVATION_RECIPE_KIND,
        schema=_recipe_artifact_schema(recipe),
        inputs=_expected_output_inputs(recipe),
        refusal_code=DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
    )
    return ref


def _read_derivation_recipe_artifact(
    store: artifacts.FileSystemCAS,
    recipe_ref: artifacts.ArtifactRef,
) -> DerivationRecipe:
    if recipe_ref.kind != DERIVATION_RECIPE_KIND or recipe_ref.media_type != "application/json":
        raise _epoch_recompute_refusal("derivation recipe artifact profile mismatch")
    try:
        recipe = DerivationRecipe.model_validate(
            _canonical_payload(store.get_bytes(recipe_ref), store=store, selector=recipe_ref)
        )
    except (OSError, TypeError, ValueError, artifacts.ArtifactOwnershipError) as exc:
        raise _epoch_recompute_refusal("derivation recipe artifact readback failed") from exc
    _verify_cached_artifact(
        store,
        artifact_ref=recipe_ref,
        expected_bytes=_canonical_bytes(recipe),
        kind=DERIVATION_RECIPE_KIND,
        schema=_recipe_artifact_schema(recipe),
        producer=_DERIVATION_PRODUCER,
        inputs=_expected_output_inputs(recipe),
        refusal_code=DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
    )
    return recipe


def load_derivation_recipe_artifact(
    store: artifacts.FileSystemCAS, recipe_ref: artifacts.ArtifactRef
) -> DerivationRecipe:
    """Reopen a selected persisted recipe and reconcile its complete contract."""
    return _read_derivation_recipe_artifact(store, recipe_ref)


def load_selected_transform_family_registry(
    store: _CertifiedDerivationReader, registry_ref: artifacts.ArtifactRef
) -> TransformFamilyRegistry:
    """Reopen one exact registry view through the canonical artifact verifier."""
    if (
        registry_ref.kind != TRANSFORM_FAMILY_REGISTRY_KIND
        or registry_ref.media_type != "application/json"
        or registry_ref.manifest_profile_sha256 is None
    ):
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            "selected transform registry reference required",
        )
    return _load_transform_family_registry_artifact(
        store,
        _manifest_projection(store, registry_ref),
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )


COMPOSITION_DERIVATION_SCHEMA_VERSION = "polisyos.core.derivations.v3"
CANDIDATE_SOURCE_SERIES_KIND = "polisyos.core.candidate_source_series"
_COMPOSITION_PRODUCER = artifacts.ProducerInfo(
    component="polisyos.core.derivations", version="3.0.0"
)
_TRANSFORM_FAMILY_REGISTRY_V3_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.transform-family-registry", version="3.0.0"
)


_COMPOSITION_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.core.derivation-composition", version="3.0.0"
)
_CANDIDATE_SOURCE_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.core.candidate-source-series", version="3.0.0"
)
InputKind = Literal["source", "candidate_source", "certified_derived"]


def _builtin_units_digest() -> str:
    return canon.fingerprint(_DEFAULT_UNITS_REGISTRY, prefix=True, canon_spec=_CANON_SPEC)


def _validate_units_selection(profile: str, ref: artifacts.ArtifactRef | None) -> None:
    if (profile == "selected_registry_bundle") != (ref is not None):
        raise ValueError("selected units profile requires its exact model registry bundle")


def _composition_units(
    store: _CertifiedDerivationReader, bundle_ref: artifacts.ArtifactRef | None
) -> UnitsRegistry:
    if bundle_ref is None:
        return _DEFAULT_UNITS_REGISTRY
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.registry.loader import load_registry_bundle
    from polisyos.ir.kernel import UnitsRegistry

    _require_selected(bundle_ref)
    _verify_resolvable_ref(store, bundle_ref)
    if bundle_ref.kind != "core.registry_bundle":
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            "unit configuration is not a model registry bundle",
        )
    try:
        bundle = load_registry_bundle(store, bundle_ref)
        if bundle.units_registry is None:
            raise ValueError("model bundle has no units registry")
        units_ref = _require_selected(bundle.units_registry)
        expected = artifacts.InputRef(
            artifact_id=units_ref.artifact_id,
            role="units_registry",
            manifest_profile_sha256=units_ref.manifest_profile_sha256,
        )
        actual = [
            item for item in store.get_manifest(bundle_ref).inputs if item.role == "units_registry"
        ]
        if actual != [expected] or units_ref.kind != "ir.units_registry":
            raise ValueError("model bundle units selection differs from its manifest")
        _verify_resolvable_ref(store, units_ref)
        return UnitsRegistry.model_validate(load_core_json_artifact(store, units_ref))
    except (OSError, ValueError, artifacts.ArtifactOwnershipError) as exc:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            "selected model units registry cannot be reconciled",
        ) from exc


def _require_composition_units(
    store: _CertifiedDerivationReader,
    bundle_ref: artifacts.ArtifactRef | None,
    bases: Iterable[BasisSignature],
    *,
    legacy_source: bool = False,
) -> None:
    units = _composition_units(store, bundle_ref).units
    for basis in bases:
        if basis.unit not in units:
            raise DerivationRefusalError(
                DerivationRefusalCode.BASIS_MISMATCH,
                f"unregistered selected model unit: {basis.unit}",
            )
        if legacy_source and units[basis.unit] != _DEFAULT_UNITS_REGISTRY.units.get(basis.unit):
            raise DerivationRefusalError(
                DerivationRefusalCode.BASIS_MISMATCH,
                f"legacy source unit definition differs: {basis.unit}",
            )


def _verify_registry_context_units(
    store: _CertifiedDerivationReader,
    projection: ArtifactContractProjection,
    context: DerivationContext,
    bases: Iterable[BasisSignature],
) -> None:
    actual = [edge for edge in projection.input_graph if edge.role == "model_registry_bundle"]
    expected = (
        []
        if context.registry_bundle_ref is None
        else list(
            _expected_input_edges(
                _selected_edges([("model_registry_bundle", context.registry_bundle_ref)])
            )
        )
    )
    if actual != expected:
        raise DerivationRefusalError(
            DerivationRefusalCode.BASIS_MISMATCH,
            "family registry and invocation unit profiles differ",
        )
    _require_composition_units(store, context.registry_bundle_ref, bases)


def _require_selected(ref: artifacts.ArtifactRef) -> artifacts.ArtifactRef:
    if ref.manifest_profile_sha256 is None:
        raise ValueError("v3 inputs require exact selected manifest profiles")
    return ref


SelectedDerivationRef = Annotated[artifacts.ArtifactRef, AfterValidator(_require_selected)]


class _CompositionRegistryPayload(_StrictModel):
    """Versioned v3 registry envelope; v2 family payload identities stay separate."""

    schema_version: Literal[COMPOSITION_DERIVATION_SCHEMA_VERSION] = (
        COMPOSITION_DERIVATION_SCHEMA_VERSION
    )
    registry: TransformFamilyRegistry


class DerivationContext(_StrictModel):
    """Exact invocation context, scope and complete requested year domain."""

    context_ref: SelectedDerivationRef
    scope_ref: SelectedDerivationRef
    years: tuple[int, ...] = Field(min_length=1)
    builtin_units_sha256: str | None = Field(
        default_factory=_builtin_units_digest,
        exclude_if=lambda x: x is None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    units_profile: Literal["builtin_v1", "selected_registry_bundle"] = "builtin_v1"
    registry_bundle_ref: SelectedDerivationRef | None = Field(
        default=None, exclude_if=lambda x: x is None
    )

    @model_validator(mode="before")
    @classmethod
    def _selected_units_omit_builtin_dependency(cls, payload: object) -> object:
        if (
            isinstance(payload, Mapping)
            and payload.get("units_profile") == "selected_registry_bundle"
        ):
            if payload.get("builtin_units_sha256") is not None:
                raise ValueError("selected model units do not depend on the builtin registry")
            return {**payload, "builtin_units_sha256": None}
        return payload

    @model_validator(mode="after")
    def _canonical_years(self) -> Self:
        if (
            self.units_profile == "builtin_v1"
            and self.builtin_units_sha256 != _builtin_units_digest()
        ):
            raise ValueError("builtin unit definitions drifted from the bound v3 profile")
        _validate_units_selection(self.units_profile, self.registry_bundle_ref)
        if self.years != tuple(sorted(set(self.years))):
            raise ValueError("context years must be unique and sorted")
        return self


class CandidateSourceSeries(_StrictModel):
    """Custodied candidate values without an empirical authority assertion."""

    schema_version: Literal[COMPOSITION_DERIVATION_SCHEMA_VERSION] = (
        COMPOSITION_DERIVATION_SCHEMA_VERSION
    )
    variable_id: str = Field(min_length=1)
    basis: BasisSignature
    points: tuple[SeriesPoint, ...]
    source_occurrence_ref: SelectedDerivationRef
    source_ref: SelectedDerivationRef
    context_ref: SelectedDerivationRef
    scope_ref: SelectedDerivationRef
    builtin_units_sha256: str | None = Field(
        default_factory=_builtin_units_digest,
        exclude_if=lambda x: x is None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    units_profile: Literal["builtin_v1", "selected_registry_bundle"] = "builtin_v1"
    registry_bundle_ref: SelectedDerivationRef | None = Field(
        default=None, exclude_if=lambda x: x is None
    )
    lineage_refs: tuple[SelectedDerivationRef, ...] = Field(min_length=1)
    evidence_status: Literal["not_established"] = "not_established"
    observation_class: Literal["candidate"] = "candidate"
    limitations: tuple[str, ...] = Field(
        default=(
            "empirical_authority_not_established",
            "source_value_correspondence_not_established",
        ),
        min_length=1,
    )

    @model_validator(mode="before")
    @classmethod
    def _selected_units_omit_builtin_dependency(cls, payload: object) -> object:
        if (
            isinstance(payload, Mapping)
            and payload.get("units_profile") == "selected_registry_bundle"
        ):
            if payload.get("builtin_units_sha256") is not None:
                raise ValueError("selected model units do not depend on the builtin registry")
            return {**payload, "builtin_units_sha256": None}
        return payload

    @model_validator(mode="after")
    def _canonical_candidate(self) -> Self:
        if (
            self.units_profile == "builtin_v1"
            and self.builtin_units_sha256 != _builtin_units_digest()
        ):
            raise ValueError("builtin unit definitions drifted from the bound v3 profile")
        _validate_units_selection(self.units_profile, self.registry_bundle_ref)
        _validate_points(self.points)
        _canonical_limitations(self.limitations)
        keys = tuple(_ref_key(ref) for ref in self.lineage_refs)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("candidate lineage refs must be unique and sorted")
        return self


class SourceDerivationInput(_StrictModel):
    """Select one legacy source without changing its declared authority contract."""

    kind: Literal["source"] = "source"
    artifact_ref: SelectedDerivationRef


class CandidateDerivationInput(_StrictModel):
    """Select one unscored candidate source artifact."""

    kind: Literal["candidate_source"] = "candidate_source"
    artifact_ref: SelectedDerivationRef


class CertifiedDerivedInput(_StrictModel):
    """Select a derived output together with its exact replayable certificate."""

    kind: Literal["certified_derived"] = "certified_derived"
    artifact_ref: SelectedDerivationRef
    certificate_ref: SelectedDerivationRef


DerivationInput = Annotated[
    SourceDerivationInput | CandidateDerivationInput | CertifiedDerivedInput,
    Field(discriminator="kind"),
]


def _ref_key(ref: artifacts.ArtifactRef) -> tuple[str, str, str, str]:
    return str(ref.artifact_id), ref.kind, ref.media_type, ref.manifest_profile_sha256 or ""


def _canonical_limitations(values: tuple[str, ...]) -> None:
    if values != tuple(sorted(set(values))) or any(not value.strip() for value in values):
        raise ValueError("limitations must be nonempty strings, unique and sorted")


def _selected_edges(refs: Sequence[tuple[str, artifacts.ArtifactRef]]) -> list[artifacts.InputRef]:
    return _sorted_input_refs(
        [
            artifacts.InputRef(
                artifact_id=ref.artifact_id,
                role=role,
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
            for role, ref in refs
        ]
    )


def _candidate_edges(series: CandidateSourceSeries) -> list[artifacts.InputRef]:
    return _selected_edges(
        [
            ("source_occurrence", series.source_occurrence_ref),
            ("source", series.source_ref),
            ("context", series.context_ref),
            ("scope", series.scope_ref),
            *(
                ([("model_registry_bundle", series.registry_bundle_ref)])
                if series.registry_bundle_ref is not None
                else []
            ),
            *((f"lineage:{index}", ref) for index, ref in enumerate(series.lineage_refs)),
        ]
    )


def persist_candidate_source_series(
    store: artifacts.FileSystemCAS,
    series: CandidateSourceSeries,
) -> artifacts.ArtifactRef:
    """Persist candidate values and exact custody lineage without minting authority."""
    series = CandidateSourceSeries.model_validate(series.model_dump(mode="python"))
    _require_composition_units(store, series.registry_bundle_ref, (series.basis,))
    return _put_or_verify(
        store,
        payload=series,
        kind=CANDIDATE_SOURCE_SERIES_KIND,
        schema=_CANDIDATE_SOURCE_SCHEMA,
        producer=_COMPOSITION_PRODUCER,
        inputs=_candidate_edges(series),
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )[0]


class CompositionRecipeInput(_StrictModel):
    """A role bound to its actual input origin and complete selected CAS profiles."""

    role: str = Field(min_length=1)
    kind: InputKind
    artifact: ArtifactContractProjection
    certificate: ArtifactContractProjection | None = Field(
        default=None, exclude_if=lambda x: x is None
    )
    basis: BasisSignature

    @model_validator(mode="after")
    def _selected_input(self) -> Self:
        _require_selected(_projection_ref(self.artifact))
        if (self.kind == "certified_derived") != (self.certificate is not None):
            raise ValueError("only certified derived inputs require a certificate")
        if self.certificate is not None:
            _require_selected(_projection_ref(self.certificate))
        return self


class CompositionRecipe(_StrictModel):
    """Version-three exact recipe; no historical source/authority coercion."""

    schema_version: Literal[COMPOSITION_DERIVATION_SCHEMA_VERSION] = (
        COMPOSITION_DERIVATION_SCHEMA_VERSION
    )
    recipe_id: str
    registry_artifact: ArtifactContractProjection
    family: TransformFamily
    inputs: tuple[CompositionRecipeInput, ...] = Field(min_length=1)
    context: DerivationContext
    output_variable_id: str = Field(min_length=1)
    output_basis: BasisSignature
    parameters: tuple[DerivedParameter, ...]
    assumptions: tuple[ResolvedAssumption, ...]

    @model_validator(mode="after")
    def _validate_recipe(self) -> Self:
        _require_selected(_projection_ref(self.registry_artifact))
        roles = tuple(item.role for item in self.inputs)
        specs = {spec.role: spec for spec in self.family.input_specs}
        if roles != tuple(sorted(set(roles))) or set(roles) != set(specs):
            raise ValueError("complete unique family AND roles are required")
        for item in self.inputs:
            if item.kind not in specs[item.role].allowed_input_kinds:
                raise ValueError(f"{item.role}: input kind not permitted by family ABI")
            if item.basis != specs[item.role].basis:
                raise ValueError(f"{item.role}: input basis differs from family ABI")
        if not _output_basis_matches_family(self.family, self.output_basis):
            raise ValueError("output basis differs from family ABI")
        if tuple(item.rule for item in self.parameters) != self.family.parameter_rules:
            raise ValueError("parameter rules differ from family ABI")
        if tuple(item.name for item in self.parameters) != tuple(
            rule.name for rule in self.family.parameter_rules
        ):
            raise ValueError("parameter names differ from family ABI")
        _validate_output_parameter_bindings(self.family, self.parameters, self.output_basis)
        if self.assumptions != _resolve_assumptions(self.family, self.parameters):
            raise ValueError("assumptions differ from family ABI")
        if self.recipe_id != _identity("derivation-recipe", self.identity_payload()):
            raise ValueError("composition recipe identity differs")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the content-bound invocation including all selected profiles."""
        return {
            key: value
            for key, value in self.model_dump(mode="python").items()
            if key != "recipe_id"
        }


class InputContribution(_StrictModel):
    """Tagged actual authority contribution; unknown is never represented as zero."""

    role: str = Field(min_length=1)
    kind: InputKind
    artifact_ref: SelectedDerivationRef
    certificate_ref: SelectedDerivationRef | None = Field(
        default=None, exclude_if=lambda x: x is None
    )
    evidence_status: Literal["established", "not_established"]
    effective_score: AuthorityScore | None = Field(default=None, exclude_if=lambda x: x is None)
    declared_ceiling: AuthorityScore | None = Field(default=None, exclude_if=lambda x: x is None)
    authority_predicate_class: Literal["consumer_asserted", "not_established"] = "not_established"
    authority_ref: artifacts.ArtifactID | None = Field(default=None, exclude_if=lambda x: x is None)
    verifier_provenance_ref: artifacts.ArtifactID | None = Field(
        default=None, exclude_if=lambda x: x is None
    )
    lineage_refs: tuple[SelectedDerivationRef, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _authority_is_typed(self) -> Self:
        _canonical_limitations(self.limitations)
        if self.evidence_status == "not_established":
            if self.effective_score is not None or not self.limitations:
                raise ValueError("unknown contribution requires limitations and absent score")
        elif self.effective_score is None:
            raise ValueError("established contribution requires a real score")
        if self.kind == "source":
            if (
                self.authority_ref is None
                or self.verifier_provenance_ref is None
                or self.authority_ref == self.verifier_provenance_ref
            ):
                raise ValueError("legacy source requires distinct declared authority/verifier refs")
            if (
                self.evidence_status != "not_established"
                or self.certificate_ref is not None
                or self.authority_predicate_class != "consumer_asserted"
                or self.declared_ceiling is None
            ):
                raise ValueError("legacy source authority remains a declared, unverified ceiling")
        elif (
            self.authority_ref is not None
            or self.verifier_provenance_ref is not None
            or self.declared_ceiling is not None
        ):
            raise ValueError("candidate/derived contributions cannot invent source authority refs")
        if self.kind == "candidate_source" and (
            self.evidence_status != "not_established" or not self.lineage_refs
        ):
            raise ValueError("candidate source must retain unknown status and lineage")
        if (self.kind == "certified_derived") != (self.certificate_ref is not None):
            raise ValueError("derived contribution requires the selected prior certificate")
        return self


class CompositionDerivedSeries(_StrictModel):
    """Derived v3 values with transitive limitations and explicit evidence status."""

    schema_version: Literal[COMPOSITION_DERIVATION_SCHEMA_VERSION] = (
        COMPOSITION_DERIVATION_SCHEMA_VERSION
    )
    variable_id: str
    basis: BasisSignature
    points: tuple[SeriesPoint, ...]
    recipe_id: str
    context: DerivationContext
    source_refs: tuple[SelectedDerivationRef, ...] = Field(min_length=1)
    observation_class: Literal["derived"] = "derived"
    evidence_status: Literal["established", "not_established"]
    effective_score: AuthorityScore | None = Field(default=None, exclude_if=lambda x: x is None)
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_output(self) -> Self:
        _validate_points(self.points)
        _canonical_limitations(self.limitations)
        if tuple(point.year for point in self.points) != self.context.years:
            raise ValueError("derived output differs from requested year domain")
        if (self.evidence_status == "established") != (self.effective_score is not None):
            raise ValueError("unknown output must omit score")
        if self.evidence_status == "not_established" and not self.limitations:
            raise ValueError("unknown output requires limitations")
        keys = tuple(_ref_key(ref) for ref in self.source_refs)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("selected source denominator must be unique and sorted")
        return self


class CompositionCertificate(_StrictModel):
    """Recomputable v3 certificate with actual tagged input contributions."""

    schema_version: Literal[COMPOSITION_DERIVATION_SCHEMA_VERSION] = (
        COMPOSITION_DERIVATION_SCHEMA_VERSION
    )
    certificate_id: str
    recipe: CompositionRecipe
    derived_artifact_ref: SelectedDerivationRef
    input_contributions: tuple[InputContribution, ...]
    evidence_status: Literal["established", "not_established"]
    effective_score: AuthorityScore | None = Field(default=None, exclude_if=lambda x: x is None)
    limitations: tuple[str, ...] = ()
    authoritative_for: Literal["certified_derived_series"] = "certified_derived_series"
    may_not_use_for: tuple[
        Literal["observed_series", "source_observation", "acquisition_passport"], ...
    ] = ("acquisition_passport", "observed_series", "source_observation")

    @model_validator(mode="after")
    def _validate_certificate(self) -> Self:
        expected = _aggregate_contributions(self.input_contributions)
        if (self.evidence_status, self.effective_score, self.limitations) != expected:
            raise ValueError("certificate authority differs from actual contributions")
        if tuple(item.role for item in self.input_contributions) != tuple(
            item.role for item in self.recipe.inputs
        ):
            raise ValueError("certificate contribution roles differ from recipe")
        if self.may_not_use_for != (
            "acquisition_passport",
            "observed_series",
            "source_observation",
        ):
            raise ValueError("composition prohibitions are fixed")
        if self.certificate_id != _identity(
            "derivation-certificate",
            {
                key: value
                for key, value in self.model_dump(mode="python").items()
                if key != "certificate_id"
            },
        ):
            raise ValueError("composition certificate identity differs")
        return self


class CompositionMaterialization(_StrictModel):
    """Persisted output and certificate selected from one exact v3 invocation."""

    recipe: CompositionRecipe
    series: CompositionDerivedSeries
    derived_artifact_ref: SelectedDerivationRef
    certificate: CompositionCertificate
    certificate_artifact_ref: SelectedDerivationRef
    cache_hit: bool


class CompositionResolution(_StrictModel):
    """Read-only replay result exposing derived values and explicit limitations."""

    certificate: CompositionCertificate
    series: CompositionDerivedSeries
    consumer_method_id: str = Field(min_length=1)
    cache_verified: Literal[True] = True


class _NormalizedInput(_StrictModel):
    kind: InputKind
    basis: BasisSignature
    points: tuple[SeriesPoint, ...]
    contribution: InputContribution
    source_refs: tuple[SelectedDerivationRef, ...]


def _aggregate_contributions(
    contributions: Sequence[InputContribution],
) -> tuple[Literal["established", "not_established"], Decimal | None, tuple[str, ...]]:
    if not contributions:
        raise ValueError("composition requires input contributions")
    limitations = tuple(sorted({value for item in contributions for value in item.limitations}))
    if any(item.evidence_status == "not_established" for item in contributions):
        return "not_established", None, limitations
    return (
        "established",
        min(item.effective_score for item in contributions if item.effective_score is not None),
        limitations,
    )


def _context_edges(context: DerivationContext) -> list[tuple[str, artifacts.ArtifactRef]]:
    return [
        ("context", context.context_ref),
        ("scope", context.scope_ref),
        *(
            ([("model_registry_bundle", context.registry_bundle_ref)])
            if context.registry_bundle_ref is not None
            else []
        ),
    ]


def _composition_edges(recipe: CompositionRecipe) -> list[artifacts.InputRef]:
    refs = [
        ("registry", _projection_ref(recipe.registry_artifact)),
        *_context_edges(recipe.context),
    ]
    for item in recipe.inputs:
        refs.append((f"input:{item.role}", _projection_ref(item.artifact)))
        if item.certificate is not None:
            refs.append((f"certificate:{item.role}", _projection_ref(item.certificate)))
    return _selected_edges(refs)


def _read_candidate(
    store: _CertifiedDerivationReader, projection: ArtifactContractProjection
) -> CandidateSourceSeries:
    from polisyos.core.artifacts import load_core_json_artifact

    ref = _projection_ref(projection)
    if _manifest_projection(store, ref) != projection:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "candidate projection drift"
        )
    try:
        series = CandidateSourceSeries.model_validate(load_core_json_artifact(store, ref))
    except (OSError, ValueError, artifacts.ArtifactOwnershipError) as exc:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "candidate read failed"
        ) from exc
    _verify_cached_artifact(
        store,
        artifact_ref=ref,
        expected_bytes=_canonical_bytes(series),
        kind=CANDIDATE_SOURCE_SERIES_KIND,
        schema=_CANDIDATE_SOURCE_SCHEMA,
        producer=_COMPOSITION_PRODUCER,
        inputs=_candidate_edges(series),
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    _require_composition_units(store, series.registry_bundle_ref, (series.basis,))
    return series


def _normalize_input(
    store: _CertifiedDerivationReader,
    *,
    role: str,
    selection: DerivationInput,
    context: DerivationContext,
    replay: _CompositionReplay,
    metadata_only: bool = False,
) -> _NormalizedInput:
    projection = _manifest_projection(store, selection.artifact_ref)
    if selection.kind == "source":
        series = _load_source(
            store, projection, refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT
        )
        contribution = InputContribution(
            role=role,
            kind="source",
            artifact_ref=selection.artifact_ref,
            evidence_status="not_established",
            declared_ceiling=series.authority.effective_score,
            authority_predicate_class="consumer_asserted",
            limitations=(
                "legacy_source_authority_not_independently_reconciled",
                "source_context_scope_correspondence_not_established",
            ),
            authority_ref=series.authority.authority_ref,
            verifier_provenance_ref=series.authority.verifier_provenance_ref,
        )
        _require_composition_units(
            store, context.registry_bundle_ref, (series.basis,), legacy_source=True
        )
        sources = (selection.artifact_ref,)
    elif selection.kind == "candidate_source":
        series = _read_candidate(store, projection)
        if _ref_key(series.context_ref) != _ref_key(context.context_ref) or _ref_key(
            series.scope_ref
        ) != _ref_key(context.scope_ref):
            raise DerivationRefusalError(
                DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
                f"{role}: candidate context/scope mismatch",
            )
        if (
            series.units_profile != context.units_profile
            or series.registry_bundle_ref != context.registry_bundle_ref
            or series.builtin_units_sha256 != context.builtin_units_sha256
        ):
            raise DerivationRefusalError(
                DerivationRefusalCode.BASIS_MISMATCH, f"{role}: candidate unit registry differs"
            )
        contribution = InputContribution(
            role=role,
            kind="candidate_source",
            artifact_ref=selection.artifact_ref,
            evidence_status="not_established",
            lineage_refs=tuple(
                {
                    _ref_key(ref): ref
                    for ref in (
                        series.source_occurrence_ref,
                        series.source_ref,
                        series.context_ref,
                        series.scope_ref,
                        *series.lineage_refs,
                    )
                }[key]
                for key in sorted(
                    {
                        _ref_key(ref)
                        for ref in (
                            series.source_occurrence_ref,
                            series.source_ref,
                            series.context_ref,
                            series.scope_ref,
                            *series.lineage_refs,
                        )
                    }
                )
            ),
            limitations=tuple(
                sorted(
                    {
                        *series.limitations,
                        "empirical_authority_not_established",
                        "source_value_correspondence_not_established",
                    }
                )
            ),
        )
        sources = (selection.artifact_ref,)
    else:
        if metadata_only:
            replay.preflight(selection.certificate_ref)
            key = _ref_key(selection.certificate_ref)
            if key in replay.results:
                certificate, series = replay.results[key].certificate, replay.results[key].series
            else:
                certificate, series = replay.prepared[key], replay.series[key]
        else:
            resolution = replay.resolve(selection.certificate_ref)
            certificate, series = resolution.certificate, resolution.series
        if (
            _ref_key(certificate.derived_artifact_ref) != _ref_key(selection.artifact_ref)
            or series.context != context
        ):
            raise DerivationRefusalError(
                DerivationRefusalCode.CERTIFICATE_DRIFT, f"{role}: certified output/context differs"
            )
        contribution = InputContribution(
            role=role,
            kind="certified_derived",
            artifact_ref=selection.artifact_ref,
            certificate_ref=selection.certificate_ref,
            evidence_status=series.evidence_status,
            effective_score=series.effective_score,
            limitations=series.limitations,
        )
        sources = series.source_refs
    if tuple(point.year for point in series.points) != context.years:
        raise DerivationRefusalError(
            DerivationRefusalCode.EXACT_YEAR_MISSING, f"{role}: exact requested year domain differs"
        )
    return _NormalizedInput(
        kind=selection.kind,
        basis=series.basis,
        points=series.points,
        contribution=contribution,
        source_refs=sources,
    )


def _selection(item: CompositionRecipeInput) -> DerivationInput:
    ref = _projection_ref(item.artifact)
    if item.kind == "source":
        return SourceDerivationInput(artifact_ref=ref)
    if item.kind == "candidate_source":
        return CandidateDerivationInput(artifact_ref=ref)
    if item.certificate is None:
        raise ValueError("derived certificate missing")
    return CertifiedDerivedInput(
        artifact_ref=ref, certificate_ref=_projection_ref(item.certificate)
    )


def _validate_expression_years(
    family: TransformFamily, parameters: Sequence[DerivedParameter], years: tuple[int, ...]
) -> None:
    values = {item.name: item.value for item in parameters}

    def visit(expression: ArithmeticExpression) -> None:
        if expression.operator == "value_at_parameter":
            year = _integer_parameter(values, expression.parameter_name or "")
            if year not in years:
                raise DerivationRefusalError(
                    DerivationRefusalCode.EXACT_YEAR_MISSING,
                    f"expression requires unselected year {year}",
                )
        for operand in expression.operands:
            visit(operand)

    visit(family.expression)


def _composition_recipe(
    store: _CertifiedDerivationReader,
    *,
    registry: TransformFamilyRegistry,
    registry_projection: ArtifactContractProjection,
    inputs: Mapping[str, DerivationInput],
    context: DerivationContext,
    output_variable_id: str,
    output_basis: BasisSignature | None,
    family_id: str | None,
    method_version: str | None,
    replay: _CompositionReplay,
) -> tuple[CompositionRecipe, dict[str, _NormalizedInput]]:
    _verify_registry_context_units(store, registry_projection, context, _registry_bases(registry))
    _verify_input_refs(
        store,
        _selected_edges(_context_edges(context)),
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    normalized = {
        role: _normalize_input(
            store,
            role=role,
            selection=selection,
            context=context,
            replay=replay,
            metadata_only=True,
        )
        for role, selection in sorted(inputs.items())
    }
    bases = {role: item.basis for role, item in normalized.items()}
    family = (
        registry.resolve_for_inputs(
            input_bases=bases,
            input_kinds={role: item.kind for role, item in normalized.items()},
            family_id=family_id,
            method_version=method_version,
        )
        if output_basis is None
        else registry.resolve(
            input_bases=bases,
            input_kinds={role: item.kind for role, item in normalized.items()},
            output_basis=output_basis,
            family_id=family_id,
            method_version=method_version,
        )
    )
    for spec in family.input_specs:
        if normalized[spec.role].kind not in spec.allowed_input_kinds:
            raise DerivationRefusalError(
                DerivationRefusalCode.BASIS_MISMATCH,
                f"{spec.role}: input kind not permitted by family ABI",
            )
        _check_constraints(spec, normalized[spec.role])
    parameters = _derive_parameters(family, normalized)
    _validate_expression_years(family, parameters, context.years)
    basis = _materialize_output_basis(family, parameters) if output_basis is None else output_basis
    _validate_output_parameter_bindings(family, parameters, basis)
    payload = {
        "schema_version": COMPOSITION_DERIVATION_SCHEMA_VERSION,
        "registry_artifact": registry_projection,
        "family": family,
        "inputs": tuple(
            CompositionRecipeInput(
                role=role,
                kind=inputs[role].kind,
                artifact=_manifest_projection(store, inputs[role].artifact_ref),
                certificate=_manifest_projection(store, inputs[role].certificate_ref)
                if isinstance(inputs[role], CertifiedDerivedInput)
                else None,
                basis=item.basis,
            )
            for role, item in normalized.items()
        ),
        "context": context,
        "output_variable_id": output_variable_id,
        "output_basis": basis,
        "parameters": parameters,
        "assumptions": _resolve_assumptions(family, parameters),
    }
    payload["recipe_id"] = _identity("derivation-recipe", payload)
    recipe = CompositionRecipe.model_validate(payload)
    selected_sources = {_ref_key(ref) for item in normalized.values() for ref in item.source_refs}
    if len(selected_sources) > replay.limits.max_selected_sources:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "recipe selected-source budget exceeded"
        )
    for selection in inputs.values():
        if isinstance(selection, CertifiedDerivedInput):
            replay.resolve(selection.certificate_ref)
    return recipe, normalized


def build_composition_recipe(
    store: artifacts.FileSystemCAS,
    *,
    registry: TransformFamilyRegistry,
    input_refs: Mapping[str, DerivationInput],
    context: DerivationContext,
    output_variable_id: str,
    output_basis: BasisSignature | None = None,
    family_id: str | None = None,
    method_version: str | None = None,
    registry_ref: artifacts.ArtifactRef,
) -> CompositionRecipe:
    """Resolve a v3 family against actual selected input kinds and exact context."""
    _require_selected(registry_ref)
    projection = _manifest_projection(store, registry_ref)
    if (
        _load_transform_family_registry_artifact(
            store, projection, refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT
        )
        != registry
    ):
        raise DerivationRefusalError(DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "registry differs")
    return _composition_recipe(
        store,
        registry=registry,
        registry_projection=projection,
        inputs=input_refs,
        context=context,
        output_variable_id=output_variable_id,
        output_basis=output_basis,
        family_id=family_id,
        method_version=method_version,
        replay=_CompositionReplay(store, DerivationEvaluationLimits()),
    )[0]


def _composition_series(
    recipe: CompositionRecipe, normalized: Mapping[str, _NormalizedInput]
) -> CompositionDerivedSeries:
    status, score, limitations = _aggregate_contributions(
        tuple(item.contribution for item in normalized.values())
    )
    refs = {_ref_key(ref): ref for item in normalized.values() for ref in item.source_refs}
    return CompositionDerivedSeries(
        variable_id=recipe.output_variable_id,
        basis=recipe.output_basis,
        points=_evaluate_points(recipe.family, recipe.parameters, normalized),
        recipe_id=recipe.recipe_id,
        context=recipe.context,
        source_refs=tuple(refs[key] for key in sorted(refs)),
        evidence_status=status,
        effective_score=score,
        limitations=limitations,
    )


def _composition_certificate(
    recipe: CompositionRecipe,
    series: CompositionDerivedSeries,
    normalized: Mapping[str, _NormalizedInput],
    ref: artifacts.ArtifactRef,
) -> CompositionCertificate:
    payload = {
        "schema_version": COMPOSITION_DERIVATION_SCHEMA_VERSION,
        "recipe": recipe,
        "derived_artifact_ref": ref,
        "input_contributions": tuple(item.contribution for item in normalized.values()),
        "evidence_status": series.evidence_status,
        "effective_score": series.effective_score,
        "limitations": series.limitations,
        "authoritative_for": "certified_derived_series",
        "may_not_use_for": ("acquisition_passport", "observed_series", "source_observation"),
    }
    # Optional scores are absent in the wire identity, including the unknown case.
    if payload["effective_score"] is None:
        del payload["effective_score"]
    payload["certificate_id"] = _identity("derivation-certificate", payload)
    return CompositionCertificate.model_validate(payload)


def _reopen_composition_recipe(
    store: _CertifiedDerivationReader, recipe: CompositionRecipe, replay: _CompositionReplay
) -> tuple[CompositionRecipe, dict[str, _NormalizedInput]]:
    recipe = CompositionRecipe.model_validate(recipe.model_dump(mode="python"))
    registry = _load_transform_family_registry_artifact(
        store, recipe.registry_artifact, refusal_code=DerivationRefusalCode.CERTIFICATE_DRIFT
    )
    rebuilt, normalized = _composition_recipe(
        store,
        registry=registry,
        registry_projection=recipe.registry_artifact,
        inputs={item.role: _selection(item) for item in recipe.inputs},
        context=recipe.context,
        output_variable_id=recipe.output_variable_id,
        output_basis=recipe.output_basis,
        family_id=recipe.family.family_id,
        method_version=recipe.family.method_version,
        replay=replay,
    )
    if rebuilt != recipe:
        raise DerivationRefusalError(
            DerivationRefusalCode.CERTIFICATE_DRIFT,
            "recipe differs from reopened full input profiles",
        )
    return rebuilt, normalized


def _bounded_recipe_replay(
    store: _CertifiedDerivationReader,
    recipe: CompositionRecipe,
    limits: DerivationEvaluationLimits | None,
) -> tuple[CompositionRecipe, dict[str, _NormalizedInput]]:
    replay = _CompositionReplay(
        store,
        limits or DerivationEvaluationLimits(),
        reserved_nodes=1,
        reserved_edges=len(recipe.inputs),
        reserved_points=len(recipe.context.years),
    )
    depth = max(
        (
            replay.preflight(_projection_ref(item.certificate))
            for item in recipe.inputs
            if item.certificate is not None
        ),
        default=0,
    )
    if depth + 1 > replay.limits.max_depth:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "combined recipe depth budget exceeded"
        )
    return _reopen_composition_recipe(store, recipe, replay)


def persist_composition_recipe_artifact(
    store: artifacts.FileSystemCAS,
    recipe: CompositionRecipe,
    *,
    limits: DerivationEvaluationLimits | None = None,
) -> artifacts.ArtifactRef:
    """Persist an independently selected v3 recipe after bounded full replay.

    Consumers must bind and load this selected reference separately when their
    contract requires recipe-artifact custody; an embedded certificate recipe
    does not establish that a separately selected recipe artifact exists.
    """
    recipe, _ = _bounded_recipe_replay(store, recipe, limits)
    ref, _ = _put_or_verify(
        store,
        payload=recipe,
        kind=DERIVATION_RECIPE_KIND,
        schema=_COMPOSITION_SCHEMA,
        producer=_COMPOSITION_PRODUCER,
        inputs=_composition_edges(recipe),
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
        force_selected=True,
    )
    return ref


def load_composition_recipe_artifact(
    store: _CertifiedDerivationReader,
    recipe_ref: artifacts.ArtifactRef,
    *,
    limits: DerivationEvaluationLimits | None = None,
) -> CompositionRecipe:
    """Verify a selected v3 recipe artifact and replay its full input chain."""
    from polisyos.core.artifacts import load_core_json_artifact

    if (
        recipe_ref.kind != DERIVATION_RECIPE_KIND
        or recipe_ref.media_type != "application/json"
        or recipe_ref.manifest_profile_sha256 is None
    ):
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            "selected composition recipe profile required",
        )
    try:
        recipe = CompositionRecipe.model_validate(load_core_json_artifact(store, recipe_ref))
        _verify_cached_artifact(
            store,
            artifact_ref=recipe_ref,
            expected_bytes=_canonical_bytes(recipe),
            kind=DERIVATION_RECIPE_KIND,
            schema=_COMPOSITION_SCHEMA,
            producer=_COMPOSITION_PRODUCER,
            inputs=_composition_edges(recipe),
            refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
        )
        return _bounded_recipe_replay(store, recipe, limits)[0]
    except DerivationRefusalError:
        raise
    except (OSError, ValueError, artifacts.ArtifactOwnershipError) as exc:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            "composition recipe artifact readback failed",
        ) from exc


def materialize_composition(
    store: artifacts.FileSystemCAS,
    recipe: CompositionRecipe,
    *,
    limits: DerivationEvaluationLimits | None = None,
) -> CompositionMaterialization:
    """Persist one certified derivation without promoting candidate authority."""
    return _materialize_composition(
        store,
        recipe,
        _CompositionReplay(
            store,
            limits or DerivationEvaluationLimits(),
            reserved_nodes=1,
            reserved_edges=len(recipe.inputs),
            reserved_points=len(recipe.context.years),
        ),
    )


def _materialize_composition(
    store: artifacts.FileSystemCAS, recipe: CompositionRecipe, replay: _CompositionReplay
) -> CompositionMaterialization:
    prior_depth = max(
        (
            replay.preflight(_projection_ref(item.certificate))
            for item in recipe.inputs
            if item.certificate is not None
        ),
        default=0,
    )
    if prior_depth + 1 > replay.limits.max_depth:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "combined composition depth budget exceeded"
        )
    recipe, normalized = _reopen_composition_recipe(store, recipe, replay)
    selected_sources = {_ref_key(ref) for item in normalized.values() for ref in item.source_refs}
    if len(selected_sources) > replay.limits.max_selected_sources:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            "composition selected-source budget exceeded",
        )
    series = _composition_series(recipe, normalized)
    edges = _composition_edges(recipe)
    derived_ref, hit = _put_or_verify(
        store,
        payload=series,
        kind=DERIVED_SERIES_KIND,
        schema=_COMPOSITION_SCHEMA,
        producer=_COMPOSITION_PRODUCER,
        inputs=edges,
        refusal_code=DerivationRefusalCode.CACHE_ARTIFACT_DRIFT,
    )
    certificate = _composition_certificate(recipe, series, normalized, derived_ref)
    certificate_ref, _ = _put_or_verify(
        store,
        payload=certificate,
        kind=DERIVATION_CERTIFICATE_KIND,
        schema=_COMPOSITION_SCHEMA,
        producer=_COMPOSITION_PRODUCER,
        inputs=[*edges, *_selected_edges([("derived_series", derived_ref)])],
        refusal_code=DerivationRefusalCode.CERTIFICATE_DRIFT,
    )
    replay.results[_ref_key(certificate_ref)] = CompositionResolution(
        certificate=certificate, series=series, consumer_method_id="core.composition.materialize"
    )
    return CompositionMaterialization(
        recipe=recipe,
        series=series,
        derived_artifact_ref=derived_ref,
        certificate=certificate,
        certificate_artifact_ref=certificate_ref,
        cache_hit=hit,
    )


class DerivationEvaluationLimits(_StrictModel):
    """Generic finite arithmetic/replay budgets mapped by higher-layer planners."""

    max_nodes: int = Field(default=128, ge=1, le=1024)
    max_depth: int = Field(default=64, ge=1, le=128)
    max_edges: int = Field(default=512, ge=1)
    max_selected_sources: int = Field(default=128, ge=1)
    max_points: int = Field(default=10000, ge=1)


class _CompositionReplay:
    def __init__(
        self,
        store: _CertifiedDerivationReader,
        limits: DerivationEvaluationLimits,
        *,
        reserved_nodes: int = 0,
        reserved_edges: int = 0,
        reserved_points: int = 0,
    ) -> None:
        if (
            reserved_nodes > limits.max_nodes
            or reserved_edges > limits.max_edges
            or reserved_points > limits.max_points
        ):
            raise DerivationRefusalError(
                DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
                "composition node/edge/point budget exceeded",
            )
        self.store = store
        self.limits = limits
        self.active: set[tuple[str, str, str, str]] = set()
        self.results: dict[tuple[str, str, str, str], CompositionResolution] = {}
        self.prepared: dict[tuple[str, str, str, str], CompositionCertificate] = {}
        self.series: dict[tuple[str, str, str, str], CompositionDerivedSeries] = {}
        self.depths: dict[tuple[str, str, str, str], int] = {}
        self.source_sets: dict[tuple[str, str, str, str], tuple[artifacts.ArtifactRef, ...]] = {}
        self.reserved_nodes = reserved_nodes
        self.edges = reserved_edges
        self.points = reserved_points
        self.sources: set[tuple[str, str, str, str]] = set()

    def preflight(self, ref: artifacts.ArtifactRef) -> int:
        """Reconcile the entire selected ancestor graph before any arithmetic."""
        from polisyos.core.artifacts import load_core_json_artifact

        _require_selected(ref)
        key = _ref_key(ref)
        if key in self.results:
            return self.depths.get(key, 1)
        if key in self.active:
            raise DerivationRefusalError(
                DerivationRefusalCode.CERTIFICATE_DRIFT, "certificate cycle"
            )
        if key in self.prepared:
            return self.depths[key]
        if (
            len(self.active) >= self.limits.max_depth
            or self.reserved_nodes + len(self.active) + len(self.prepared) >= self.limits.max_nodes
        ):
            raise DerivationRefusalError(
                DerivationRefusalCode.CERTIFICATE_DRIFT,
                "combined certificate node/depth budget exceeded",
            )
        self.active.add(key)
        try:
            certificate = CompositionCertificate.model_validate(
                load_core_json_artifact(self.store, ref)
            )
            recipe = certificate.recipe
            self.edges += len(recipe.inputs)
            self.points += len(recipe.context.years)
            if self.edges > self.limits.max_edges or self.points > self.limits.max_points:
                raise DerivationRefusalError(
                    DerivationRefusalCode.CERTIFICATE_DRIFT,
                    "combined certificate edge/point budget exceeded",
                )
            registry = _load_transform_family_registry_artifact(
                self.store,
                recipe.registry_artifact,
                refusal_code=DerivationRefusalCode.CERTIFICATE_DRIFT,
            )
            _verify_registry_context_units(
                self.store, recipe.registry_artifact, recipe.context, _registry_bases(registry)
            )
            family = registry.resolve(
                input_bases={item.role: item.basis for item in recipe.inputs},
                input_kinds={item.role: item.kind for item in recipe.inputs},
                output_basis=recipe.output_basis,
                family_id=recipe.family.family_id,
                method_version=recipe.family.method_version,
            )
            if family != recipe.family:
                raise DerivationRefusalError(
                    DerivationRefusalCode.CERTIFICATE_DRIFT,
                    "embedded family differs from selected registry",
                )
            _verify_input_refs(
                self.store,
                _selected_edges(_context_edges(recipe.context)),
                refusal_code=DerivationRefusalCode.CERTIFICATE_DRIFT,
            )
            refs: dict[tuple[str, str, str, str], artifacts.ArtifactRef] = {}
            child_depth = 0
            leaf_inputs: dict[str, _SeriesValues] = {}
            for item in recipe.inputs:
                if (
                    _manifest_projection(self.store, _projection_ref(item.artifact))
                    != item.artifact
                ):
                    raise DerivationRefusalError(
                        DerivationRefusalCode.CERTIFICATE_DRIFT, "selected input projection differs"
                    )
                if item.kind == "certified_derived":
                    if item.certificate is None:
                        raise ValueError("prior certificate missing")
                    prior_ref = _projection_ref(item.certificate)
                    if _manifest_projection(self.store, prior_ref) != item.certificate:
                        raise DerivationRefusalError(
                            DerivationRefusalCode.CERTIFICATE_DRIFT,
                            "selected certificate projection differs",
                        )
                    child_depth = max(child_depth, self.preflight(prior_ref))
                    prior_key = _ref_key(prior_ref)
                    prior = self.prepared.get(prior_key)
                    prior_recipe = (
                        prior.recipe
                        if prior is not None
                        else self.results[prior_key].certificate.recipe
                    )
                    output_ref = (
                        prior.derived_artifact_ref
                        if prior is not None
                        else self.results[prior_key].certificate.derived_artifact_ref
                    )
                    if (
                        _ref_key(output_ref) != _ref_key(_projection_ref(item.artifact))
                        or prior_recipe.context != recipe.context
                        or prior_recipe.output_basis != item.basis
                    ):
                        raise DerivationRefusalError(
                            DerivationRefusalCode.CERTIFICATE_DRIFT,
                            "prior output/context/basis differs",
                        )
                    prior_sources = self.source_sets.get(
                        prior_key,
                        self.results[prior_key].series.source_refs
                        if prior_key in self.results
                        else (),
                    )
                    refs.update((_ref_key(source), source) for source in prior_sources)
                    leaf_inputs[item.role] = _YearDomain(
                        points=tuple(
                            SeriesPoint(year=year, value=Decimal(0))
                            for year in recipe.context.years
                        )
                    )
                else:
                    normalized = _normalize_input(
                        self.store,
                        role=item.role,
                        selection=_selection(item),
                        context=recipe.context,
                        replay=self,
                    )
                    if normalized.basis != item.basis:
                        raise DerivationRefusalError(
                            DerivationRefusalCode.BASIS_MISMATCH, "actual leaf basis differs"
                        )
                    _check_constraints(
                        next(spec for spec in family.input_specs if spec.role == item.role),
                        normalized,
                    )
                    leaf_inputs[item.role] = normalized
                    refs.update((_ref_key(source), source) for source in normalized.source_refs)
            _validate_expression_years(family, recipe.parameters, recipe.context.years)
            if _derive_parameters(family, leaf_inputs) != recipe.parameters:
                raise DerivationRefusalError(
                    DerivationRefusalCode.CERTIFICATE_DRIFT,
                    "parameters differ from exact year domain",
                )
            depth = child_depth + 1
            if depth > self.limits.max_depth:
                raise DerivationRefusalError(
                    DerivationRefusalCode.CERTIFICATE_DRIFT,
                    "combined certificate depth budget exceeded",
                )
            self.sources.update(refs)
            if len(self.sources) > self.limits.max_selected_sources:
                raise DerivationRefusalError(
                    DerivationRefusalCode.CERTIFICATE_DRIFT, "selected source budget exceeded"
                )
            series = CompositionDerivedSeries.model_validate(
                load_core_json_artifact(self.store, certificate.derived_artifact_ref)
            )
            if (
                series.recipe_id != recipe.recipe_id
                or series.context != recipe.context
                or series.basis != recipe.output_basis
                or series.variable_id != recipe.output_variable_id
                or tuple(_ref_key(source) for source in series.source_refs) != tuple(sorted(refs))
            ):
                raise DerivationRefusalError(
                    DerivationRefusalCode.CERTIFICATE_DRIFT,
                    "output identity/domain/source denominator differs",
                )
            edges = _composition_edges(recipe)
            _verify_cached_artifact(
                self.store,
                artifact_ref=certificate.derived_artifact_ref,
                expected_bytes=_canonical_bytes(series),
                kind=DERIVED_SERIES_KIND,
                schema=_COMPOSITION_SCHEMA,
                producer=_COMPOSITION_PRODUCER,
                inputs=edges,
                refusal_code=DerivationRefusalCode.CACHE_ARTIFACT_DRIFT,
            )
            _verify_cached_artifact(
                self.store,
                artifact_ref=ref,
                expected_bytes=_canonical_bytes(certificate),
                kind=DERIVATION_CERTIFICATE_KIND,
                schema=_COMPOSITION_SCHEMA,
                producer=_COMPOSITION_PRODUCER,
                inputs=[
                    *edges,
                    *_selected_edges([("derived_series", certificate.derived_artifact_ref)]),
                ],
                refusal_code=DerivationRefusalCode.CERTIFICATE_DRIFT,
            )
            self.prepared[key] = certificate
            self.series[key] = series
            self.depths[key] = depth
            self.source_sets[key] = tuple(refs[index] for index in sorted(refs))
            return depth
        except DerivationRefusalError:
            raise
        except (OSError, ValueError, artifacts.ArtifactOwnershipError) as exc:
            raise DerivationRefusalError(
                DerivationRefusalCode.CERTIFICATE_DRIFT, "composition certificate preflight failed"
            ) from exc
        finally:
            self.active.remove(key)

    def resolve(self, ref: artifacts.ArtifactRef) -> CompositionResolution:
        key = _ref_key(ref)
        if key in self.results:
            return self.results[key]
        self.preflight(ref)
        certificate = self.prepared[key]
        recipe, normalized = _reopen_composition_recipe(self.store, certificate.recipe, self)
        series = _composition_series(recipe, normalized)
        expected = _composition_certificate(
            recipe, series, normalized, certificate.derived_artifact_ref
        )
        if certificate != expected:
            raise DerivationRefusalError(
                DerivationRefusalCode.CERTIFICATE_DRIFT, "contributions differ after replay"
            )
        _verify_cached_artifact(
            self.store,
            artifact_ref=certificate.derived_artifact_ref,
            expected_bytes=_canonical_bytes(series),
            kind=DERIVED_SERIES_KIND,
            schema=_COMPOSITION_SCHEMA,
            producer=_COMPOSITION_PRODUCER,
            inputs=_composition_edges(recipe),
            refusal_code=DerivationRefusalCode.CACHE_ARTIFACT_DRIFT,
        )
        result = CompositionResolution(
            certificate=certificate, series=series, consumer_method_id="core.composition.replay"
        )
        self.results[key] = result
        return result


def resolve_certified_composition(
    store: _CertifiedDerivationReader,
    *,
    certificate_ref: artifacts.ArtifactRef,
    consumer_method_id: str,
    limits: DerivationEvaluationLimits | None = None,
) -> CompositionResolution:
    """Freshly replay the complete selected certificate chain before consumption."""
    if not consumer_method_id.strip():
        raise ValueError("consumer method id must be nonempty")
    result = _CompositionReplay(store, limits or DerivationEvaluationLimits()).resolve(
        certificate_ref
    )
    return CompositionResolution(
        certificate=result.certificate, series=result.series, consumer_method_id=consumer_method_id
    )


class DerivationDagInput(_StrictModel):
    """One selected supplier for one required AND role; alternatives are upstream."""

    role: str = Field(min_length=1)
    selection: DerivationInput | None = None
    node_id: str | None = None

    @model_validator(mode="after")
    def _one_supplier(self) -> Self:
        if (self.selection is None) == (self.node_id is None):
            raise ValueError("exactly one selected input or predecessor node is required")
        return self


class DerivationDagNode(_StrictModel):
    """One registered family application in an explicitly selected arithmetic DAG."""

    node_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    output_variable_id: str = Field(min_length=1)
    output_basis: BasisSignature | None = None
    inputs: tuple[DerivationDagInput, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_roles(self) -> Self:
        roles = tuple(item.role for item in self.inputs)
        if roles != tuple(sorted(set(roles))):
            raise ValueError("DAG roles must be unique and sorted")
        return self


class DerivationDagMaterialization(_StrictModel):
    """Topologically ordered persisted node results and the exact selected root."""

    root_node_id: str
    node_ids: tuple[str, ...]
    materializations: tuple[CompositionMaterialization, ...]

    @property
    def root(self) -> CompositionMaterialization:
        """Return the selected root materialization."""
        return self.materializations[self.node_ids.index(self.root_node_id)]


def materialize_derivation_dag(
    store: artifacts.FileSystemCAS,
    *,
    registry: TransformFamilyRegistry,
    registry_ref: artifacts.ArtifactRef,
    nodes: Sequence[DerivationDagNode],
    root_node_id: str,
    context: DerivationContext,
    limits: DerivationEvaluationLimits | None = None,
) -> DerivationDagMaterialization:
    """Prevalidate one bounded selected DAG, then persist ordinary per-node outputs."""
    limits = limits or DerivationEvaluationLimits()
    by_id = {node.node_id: node for node in nodes}
    if len(by_id) != len(nodes) or root_node_id not in by_id:
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "duplicate nodes or absent root"
        )
    if (
        len(nodes) > limits.max_nodes
        or sum(len(node.inputs) for node in nodes) > limits.max_edges
        or len(nodes) * len(context.years) > limits.max_points
    ):
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "DAG node/edge/point budget exceeded"
        )
    order: list[str] = []
    active: set[str] = set()
    depths: dict[str, int] = {}

    def visit(node_id: str) -> int:
        if node_id in active:
            raise DerivationRefusalError(DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "DAG cycle")
        if node_id in depths:
            return depths[node_id]
        if node_id not in by_id:
            raise DerivationRefusalError(
                DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "DAG predecessor missing"
            )
        if len(active) >= limits.max_depth:
            raise DerivationRefusalError(
                DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "DAG depth budget exceeded"
            )
        active.add(node_id)
        depth = 1 + max(
            (visit(item.node_id) for item in by_id[node_id].inputs if item.node_id is not None),
            default=0,
        )
        active.remove(node_id)
        if depth > limits.max_depth:
            raise DerivationRefusalError(
                DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "DAG depth budget exceeded"
            )
        depths[node_id] = depth
        order.append(node_id)
        return depth

    visit(root_node_id)
    if len(order) != len(nodes):
        raise DerivationRefusalError(
            DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
            "DAG contains nodes unreachable from selected root",
        )
    _require_selected(registry_ref)
    projection = _manifest_projection(store, registry_ref)
    if (
        _load_transform_family_registry_artifact(
            store, projection, refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT
        )
        != registry
    ):
        raise DerivationRefusalError(DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "registry differs")
    _verify_registry_context_units(store, projection, context, _registry_bases(registry))
    _verify_input_refs(
        store,
        _selected_edges(_context_edges(context)),
        refusal_code=DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
    )
    replay = _CompositionReplay(
        store,
        limits,
        reserved_nodes=len(nodes),
        reserved_edges=sum(len(node.inputs) for node in nodes),
        reserved_points=len(nodes) * len(context.years),
    )
    bases: dict[str, BasisSignature] = {}
    selected_sources: set[tuple[str, str, str, str]] = set()
    external_depths: dict[str, int] = {}
    for node_id in order:
        node = by_id[node_id]
        dependency_depths = []
        for item in node.inputs:
            if isinstance(item.selection, CertifiedDerivedInput):
                dependency_depths.append(replay.preflight(item.selection.certificate_ref))
            elif item.node_id is not None:
                dependency_depths.append(external_depths[item.node_id])
        external_depths[node_id] = 1 + max(dependency_depths, default=0)
        if external_depths[node_id] > limits.max_depth:
            raise DerivationRefusalError(
                DerivationRefusalCode.INPUT_ARTIFACT_DRIFT,
                "combined DAG/certificate depth budget exceeded",
            )
    for node_id in order:
        node = by_id[node_id]
        inputs = {
            item.role: _normalize_input(
                store,
                role=item.role,
                selection=item.selection,
                context=context,
                replay=replay,
                metadata_only=True,
            )
            for item in node.inputs
            if item.selection is not None
        }
        input_bases = {
            item.role: bases[item.node_id] if item.node_id is not None else inputs[item.role].basis
            for item in node.inputs
        }
        family = (
            registry.resolve_for_inputs(
                input_bases=input_bases,
                input_kinds={
                    item.role: "certified_derived"
                    if item.node_id is not None
                    else inputs[item.role].kind
                    for item in node.inputs
                },
                family_id=node.family_id,
                method_version=node.method_version,
            )
            if node.output_basis is None
            else registry.resolve(
                input_bases=input_bases,
                input_kinds={
                    item.role: "certified_derived"
                    if item.node_id is not None
                    else inputs[item.role].kind
                    for item in node.inputs
                },
                output_basis=node.output_basis,
                family_id=node.family_id,
                method_version=node.method_version,
            )
        )
        for item in node.inputs:
            spec = next(spec for spec in family.input_specs if spec.role == item.role)
            kind = "certified_derived" if item.node_id is not None else inputs[item.role].kind
            if kind not in spec.allowed_input_kinds:
                raise DerivationRefusalError(
                    DerivationRefusalCode.BASIS_MISMATCH,
                    f"{item.role}: input kind not permitted by family ABI",
                )
        for item in inputs.values():
            selected_sources.update(_ref_key(ref) for ref in item.source_refs)
        if len(selected_sources) > limits.max_selected_sources:
            raise DerivationRefusalError(
                DerivationRefusalCode.INPUT_ARTIFACT_DRIFT, "DAG selected-source budget exceeded"
            )
        # Parameters depend only on the exact year domain or registered literals.
        year_values = _YearDomain(
            points=tuple(SeriesPoint(year=year, value=Decimal(0)) for year in context.years)
        )
        parameters = _derive_parameters(family, dict.fromkeys(input_bases, year_values))
        _validate_expression_years(family, parameters, context.years)
        bases[node_id] = _materialize_output_basis(family, parameters)
        if node.output_basis is not None:
            _validate_output_parameter_bindings(family, parameters, node.output_basis)
            bases[node_id] = node.output_basis
    results: dict[str, CompositionMaterialization] = {}
    for node_id in order:
        node = by_id[node_id]
        selections: dict[str, DerivationInput] = {}
        for item in node.inputs:
            if item.node_id is not None:
                prior = results[item.node_id]
                selections[item.role] = CertifiedDerivedInput(
                    artifact_ref=prior.derived_artifact_ref,
                    certificate_ref=prior.certificate_artifact_ref,
                )
            elif item.selection is not None:
                selections[item.role] = item.selection
        recipe, _ = _composition_recipe(
            store,
            registry=registry,
            registry_projection=projection,
            inputs=selections,
            context=context,
            output_variable_id=node.output_variable_id,
            output_basis=node.output_basis,
            family_id=node.family_id,
            method_version=node.method_version,
            replay=replay,
        )
        results[node_id] = _materialize_composition(store, recipe, replay)
        result = results[node_id]
        replay.depths[_ref_key(result.certificate_artifact_ref)] = external_depths[node_id]
    return DerivationDagMaterialization(
        root_node_id=root_node_id,
        node_ids=tuple(order),
        materializations=tuple(results[node_id] for node_id in order),
    )


class _YearDomain(_StrictModel):
    points: tuple[SeriesPoint, ...]


__all__ = [
    "CANDIDATE_SOURCE_SERIES_KIND",
    "COMPOSITION_DERIVATION_SCHEMA_VERSION",
    "DERIVATION_CERTIFICATE_KIND",
    "DERIVATION_RECIPE_KIND",
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
    "CandidateDerivationInput",
    "CandidateSourceSeries",
    "CertificateInputAuthority",
    "CertifiedDerivationConsumption",
    "CertifiedDerivationResolution",
    "CertifiedDerivedInput",
    "CompositionCertificate",
    "CompositionDerivedSeries",
    "CompositionMaterialization",
    "CompositionRecipe",
    "CompositionRecipeInput",
    "CompositionResolution",
    "DerivationCertificate",
    "DerivationContext",
    "DerivationDagInput",
    "DerivationDagMaterialization",
    "DerivationDagNode",
    "DerivationEvaluationLimits",
    "DerivationInput",
    "DerivationMaterialization",
    "DerivationRecipe",
    "DerivationRefusalCode",
    "DerivationRefusalError",
    "DerivationRefusalReason",
    "DerivedParameter",
    "DerivedSeries",
    "InputContribution",
    "ParameterRule",
    "RecipeInput",
    "ResolvedAssumption",
    "SeriesPoint",
    "SourceDerivationInput",
    "SourceSeries",
    "TransformFamily",
    "TransformFamilyRegistry",
    "TransformInputSpec",
    "build_composition_recipe",
    "build_derivation_recipe",
    "consume_certified_derivation",
    "load_composition_recipe_artifact",
    "load_derivation_recipe_artifact",
    "load_selected_transform_family_registry",
    "load_transform_family_registry",
    "materialize_composition",
    "materialize_derivation",
    "materialize_derivation_dag",
    "persist_candidate_source_series",
    "persist_composition_recipe_artifact",
    "persist_derivation_recipe_artifact",
    "persist_source_series",
    "persist_transform_family_registry",
    "resolve_certified_composition",
    "resolve_certified_derivation",
]
