"""Selected candidate semantics for a registered annual-flow composition.

The finite ratio-times-denominator relation uses role names and semantic bases
from a selected registration. Source projection, arithmetic, and empirical
authority remain separate predicates; a replayed value never supplies a score.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactStore,
    CoreJSONArtifactStore,
    InputRef,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef
from polisyos.ir.kernel import MoneyUnit, UnitsRegistry

from .semantic_derived_binding import DerivedInputCorrespondenceRef, DerivedInputProfileRef
from .variable_binding import (
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    ModelInputScope,
    ScopedMeasurementOccurrence,
    ScopedMeasurementOccurrenceRef,
    ScopedSourceSelection,
    SelectedVariableBindingRef,
    VariableRepresentation,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
)

if TYPE_CHECKING:
    from polisyos.core.derivations import (
        CandidateSourceSeries,
        CompositionDerivedSeries,
        CompositionRecipe,
        TransformFamily,
    )

    from .model_input_requirements import ModelInputObligation


_ROLE_PATTERN = r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$"


class _CompositionContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    def lineage_inputs(self) -> list[InputRef]:
        """Return this contract's complete ordered selected dependencies."""
        return []

    def require_lineage(self, manifest: ArtifactManifest) -> None:
        """Refuse omitted, grafted, duplicate, or additional dependency edges."""
        if manifest.inputs != self.lineage_inputs():
            raise ValueError("composition_input_semantic_lineage_mismatch")


class RegisteredDerivedInputProfileRef(DerivedInputProfileRef):
    """Exact selected version-two semantic operator registration."""


class RegisteredDerivedInputContextRef(SelectedVariableBindingRef):
    """Exact candidate invocation and individually named source scopes."""

    kind: Literal["catalog.registered_derivation_context"] = "catalog.registered_derivation_context"
    media_type: Literal["application/json"] = "application/json"


class NativeDerivationSourceProjectionRef(SelectedVariableBindingRef):
    """Selected source-value/basis projection, independently replayed on use."""

    kind: Literal["catalog.native_derivation_source_projection"] = (
        "catalog.native_derivation_source_projection"
    )
    media_type: Literal["application/json"] = "application/json"


class RegisteredSemanticBasis(_CompositionContract):
    """Selected semantic coordinates declared at one registered operator edge."""

    semantic_definition_ref: VariableSemanticDefinitionRef
    representation_ref: VariableRepresentationRef
    binding_profile_ref: MeasurementBindingProfileRef

    def selected_inputs(self, prefix: str) -> list[InputRef]:
        """Return the edge's exact semantic dependencies under its role."""
        return [
            input_ref_from_artifact_ref(ref, role=f"{prefix}.{suffix}")
            for suffix, ref in (
                ("definition", self.semantic_definition_ref),
                ("representation", self.representation_ref),
                ("binding_profile", self.binding_profile_ref),
            )
        ]


class RegisteredDerivationRoleBasis(_CompositionContract):
    """One exact family role and the selected source meaning it consumes."""

    role: str = Field(pattern=_ROLE_PATTERN)
    basis: RegisteredSemanticBasis


class RegisteredDerivedInputProfile(_CompositionContract):
    """One selected ratio/denominator registration with explicit role identities.

    This first relation admits annual calendar monetary totals. Other arithmetic
    families and composed intermediate meanings require their own semantic
    profiles; an arithmetic certificate alone cannot supply that correspondence.
    """

    ARTIFACT_KIND: ClassVar[str] = "catalog.derived_input_profile"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.catalog.RegisteredDerivedInputProfile"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "2.0"

    schema_version: Literal["2.0"] = "2.0"
    relation_profile: Literal["ratio_times_denominator.annual_calendar_flow.v1"] = (
        "ratio_times_denominator.annual_calendar_flow.v1"
    )
    registry_ref: SelectedVariableBindingRef
    family_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    ratio_role: str = Field(pattern=_ROLE_PATTERN)
    denominator_role: str = Field(pattern=_ROLE_PATTERN)
    inputs: tuple[RegisteredDerivationRoleBasis, ...] = Field(min_length=2, max_length=2)
    output: RegisteredSemanticBasis
    output_projection: Literal["scalar"] = "scalar"
    authority_purpose: Literal["candidate_simulation_input_only"] = (
        "candidate_simulation_input_only"
    )

    @model_validator(mode="after")
    def _registered_roles(self) -> RegisteredDerivedInputProfile:
        roles = tuple(item.role for item in self.inputs)
        if (
            self.registry_ref.kind != "polisyos.runtime.transform_family_registry"
            or self.registry_ref.media_type != "application/json"
            or roles != tuple(sorted(set(roles)))
            or self.ratio_role == self.denominator_role
            or set(roles) != {self.ratio_role, self.denominator_role}
        ):
            raise ValueError("composition_input_registered_role_set_mismatch")
        return self

    def lineage_inputs(self) -> list[InputRef]:
        """Bind the exact operator registry and all source/output meanings."""
        return [
            input_ref_from_artifact_ref(self.registry_ref, role="operator.registry"),
            *(edge for item in self.inputs for edge in item.basis.selected_inputs(item.role)),
            *self.output.selected_inputs("output"),
        ]


class RegisteredMeasurementRole(_CompositionContract):
    """An actual selected occurrence for one named registration role."""

    role: str = Field(pattern=_ROLE_PATTERN)
    occurrence_ref: ScopedMeasurementOccurrenceRef


class RegisteredDerivedModelInputRequest(_CompositionContract):
    """One complete port derivation in an atomic selected-invocation batch."""

    model_input_obligation_ref: SelectedVariableBindingRef
    profile_ref: RegisteredDerivedInputProfileRef
    role_occurrences: tuple[RegisteredMeasurementRole, ...] = Field(min_length=2, max_length=2)
    binding_id: str = Field(pattern=r"^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}$")
    derivation_bundle_ref: SelectedVariableBindingRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _selected_request(self) -> RegisteredDerivedModelInputRequest:
        if (
            self.model_input_obligation_ref.kind != "runtime.quality.model_input_obligation"
            or self.model_input_obligation_ref.media_type != "application/json"
        ):
            raise ValueError("composition_input_request_obligation_kind_mismatch")
        roles = tuple(item.role for item in self.role_occurrences)
        if roles != tuple(sorted(set(roles))):
            raise ValueError("composition_input_request_role_set_mismatch")
        if self.derivation_bundle_ref is not None and (
            self.derivation_bundle_ref.kind != "runtime.quality.n7_derivation_bundle"
            or self.derivation_bundle_ref.media_type != "application/json"
        ):
            raise ValueError("composition_input_request_bundle_kind_mismatch")
        return self


class RegisteredRoleScope(_CompositionContract):
    """A role-specific population and exact geography/period/time semantics."""

    role: str = Field(pattern=_ROLE_PATTERN)
    scope: ModelInputScope


class RegisteredDerivedInputContext(_CompositionContract):
    """Exact candidate target and role scopes, without empirical coupling truth.

    The complete context is also the Core composition's shared scope selection.
    Its role scopes remain distinct: the numerator population need not equal
    the denominator population. No provider release/base relationship is
    invented when the selected registration does not establish one.
    """

    ARTIFACT_KIND: ClassVar[str] = "catalog.registered_derivation_context"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.catalog.RegisteredDerivedInputContext"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    schema_version: Literal["1.0"] = "1.0"
    profile_ref: RegisteredDerivedInputProfileRef
    obligation_set_ref: SelectedVariableBindingRef
    model_input_obligation_ref: SelectedVariableBindingRef
    model_interface_ref: SelectedVariableBindingRef
    model_port_id: str = Field(min_length=1)
    registry_bundle_ref: SelectedVariableBindingRef
    year: int = Field(ge=1900, le=2200, strict=True)
    output_scope: ModelInputScope
    roles: tuple[RegisteredMeasurementRole, ...] = Field(min_length=2, max_length=2)
    role_scopes: tuple[RegisteredRoleScope, ...] = Field(min_length=2, max_length=2)
    empirical_context: Literal["not_established"] = "not_established"
    uncertainty_status: Literal["not_established"] = "not_established"
    authority_purpose: Literal["candidate_simulation_input_only"] = (
        "candidate_simulation_input_only"
    )

    @model_validator(mode="after")
    def _exact_subject_and_roles(self) -> RegisteredDerivedInputContext:
        for ref, kind in (
            (self.obligation_set_ref, "runtime.quality.model_input_obligation_set"),
            (self.model_input_obligation_ref, "runtime.quality.model_input_obligation"),
            (self.model_interface_ref, "runtime.quality.program_graph_input_interface"),
            (self.registry_bundle_ref, "core.registry_bundle"),
        ):
            if ref.kind != kind or ref.media_type != "application/json":
                raise ValueError("composition_input_context_kind_mismatch")
        roles = tuple(item.role for item in self.roles)
        if (
            roles != tuple(sorted(set(roles)))
            or tuple(item.role for item in self.role_scopes) != roles
        ):
            raise ValueError("composition_input_context_role_set_mismatch")
        return self

    def lineage_inputs(self) -> list[InputRef]:
        """Bind the target, units owner and every exact role occurrence."""
        return [
            input_ref_from_artifact_ref(ref, role=role)
            for role, ref in (
                ("semantic_profile", self.profile_ref),
                ("target.obligation_set", self.obligation_set_ref),
                ("target.obligation", self.model_input_obligation_ref),
                ("target.interface", self.model_interface_ref),
                ("model.registry_bundle", self.registry_bundle_ref),
                *((f"{item.role}.occurrence", item.occurrence_ref) for item in self.roles),
            )
        ]


class NativeDerivationSourceProjection(_CompositionContract):
    """Recomputed native source point and basis; empirical authority stays unknown."""

    ARTIFACT_KIND: ClassVar[str] = "catalog.native_derivation_source_projection"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.catalog.NativeDerivationSourceProjection"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    schema_version: Literal["1.0"] = "1.0"
    profile_ref: RegisteredDerivedInputProfileRef
    context_ref: RegisteredDerivedInputContextRef
    role: str = Field(pattern=_ROLE_PATTERN)
    occurrence_ref: ScopedMeasurementOccurrenceRef
    source_basis: RegisteredSemanticBasis
    source_variable_id: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2200, strict=True)
    canonical_value: Decimal = Field(allow_inf_nan=False, strict=True)
    quantity_kind: Literal["flow"] = "flow"
    unit_id: str = Field(min_length=1)
    source_value_correspondence: Literal["recomputed"] = "recomputed"
    source_basis_correspondence: Literal["recomputed"] = "recomputed"
    empirical_authority: Literal["not_established"] = "not_established"
    authority_purpose: Literal["candidate_simulation_input_only"] = (
        "candidate_simulation_input_only"
    )

    def lineage_inputs(self) -> list[InputRef]:
        """Bind the exact selected predicate inputs, without authority-score refs."""
        return [
            input_ref_from_artifact_ref(self.profile_ref, role="semantic_profile"),
            input_ref_from_artifact_ref(self.context_ref, role="context"),
            input_ref_from_artifact_ref(self.occurrence_ref, role="source.occurrence"),
            *self.source_basis.selected_inputs("source"),
        ]


class CandidateDerivedMeasurementRole(_CompositionContract):
    """One registered role's unscored source and its exact native projection."""

    role: str = Field(pattern=_ROLE_PATTERN)
    source_series_ref: SelectedVariableBindingRef
    source_projection_ref: NativeDerivationSourceProjectionRef

    @model_validator(mode="after")
    def _candidate_kind(self) -> CandidateDerivedMeasurementRole:
        if (
            self.source_series_ref.kind != "polisyos.core.candidate_source_series"
            or self.source_series_ref.media_type != "application/json"
        ):
            raise ValueError("composition_input_candidate_source_kind_mismatch")
        return self

    def lineage_inputs(self) -> list[InputRef]:
        """Bind the role to both the arithmetic source and its source predicates."""
        return [
            input_ref_from_artifact_ref(self.source_series_ref, role=f"{self.role}.source_series"),
            input_ref_from_artifact_ref(
                self.source_projection_ref, role=f"{self.role}.source_projection"
            ),
        ]


class RegisteredDerivedInputCorrespondence(_CompositionContract):
    """One selected v3 output, complete recipe and candidate semantic subjects."""

    ARTIFACT_KIND: ClassVar[str] = "catalog.derived_input_correspondence"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.catalog.RegisteredDerivedInputCorrespondence"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "2.0"

    schema_version: Literal["2.0"] = "2.0"
    profile_ref: RegisteredDerivedInputProfileRef
    context_ref: RegisteredDerivedInputContextRef
    model_input_obligation_ref: SelectedVariableBindingRef
    model_interface_ref: SelectedVariableBindingRef
    model_port_id: str = Field(min_length=1)
    recipe_ref: SelectedVariableBindingRef
    certificate_ref: SelectedVariableBindingRef
    output_ref: SelectedVariableBindingRef
    year: int = Field(ge=1900, le=2200, strict=True)
    roles: tuple[CandidateDerivedMeasurementRole, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def _selected_artifacts(self) -> RegisteredDerivedInputCorrespondence:
        for ref, kind in (
            (self.model_input_obligation_ref, "runtime.quality.model_input_obligation"),
            (self.model_interface_ref, "runtime.quality.program_graph_input_interface"),
            (self.recipe_ref, "polisyos.runtime.derivation_recipe"),
            (self.certificate_ref, "polisyos.runtime.derivation_certificate"),
            (self.output_ref, "polisyos.runtime.derived_economic_series"),
        ):
            if ref.kind != kind or ref.media_type != "application/json":
                raise ValueError("composition_input_selected_kind_mismatch")
        roles = tuple(item.role for item in self.roles)
        if roles != tuple(sorted(set(roles))):
            raise ValueError("composition_input_role_set_mismatch")
        return self

    def lineage_inputs(self) -> list[InputRef]:
        """Return all operator, source, target and persisted arithmetic edges."""
        return [
            *(
                input_ref_from_artifact_ref(ref, role=role)
                for role, ref in (
                    ("semantic_profile", self.profile_ref),
                    ("context", self.context_ref),
                    ("target.obligation", self.model_input_obligation_ref),
                    ("target.interface", self.model_interface_ref),
                    ("derivation.recipe", self.recipe_ref),
                    ("derivation.certificate", self.certificate_ref),
                    ("derivation.output", self.output_ref),
                )
            ),
            *(edge for item in self.roles for edge in item.lineage_inputs()),
        ]


@dataclass(frozen=True)
class ReplayedCandidateDerivationRole:
    """Owner-loaded inputs for the pure source and composition predicates."""

    selection: CandidateDerivedMeasurementRole
    projection: NativeDerivationSourceProjection
    occurrence: ScopedMeasurementOccurrence
    replayed_occurrence: ScopedMeasurementOccurrence
    source_selection: ScopedSourceSelection
    definition: VariableSemanticDefinition
    representation: VariableRepresentation
    binding_profile: MeasurementBindingProfile
    series: CandidateSourceSeries


class RegisteredDerivedInputEvaluation(_CompositionContract):
    """Separate candidate arithmetic/source facts from empirical authority."""

    status: Literal["candidate", "refused"]
    structural_correspondence: Literal["recomputed", "not_established"]
    empirical_context: Literal["not_established"] = "not_established"
    uncertainty_status: Literal["not_established"] = "not_established"
    authority_purpose: Literal["candidate_simulation_input_only"] = (
        "candidate_simulation_input_only"
    )
    value: Decimal | None = None
    limitation_codes: tuple[str, ...] = ()
    refusal_codes: tuple[str, ...] = ()
    may_not_use_for: tuple[
        Literal["claim_evidence", "publication", "observed_measurement", "source_currentness"], ...
    ] = ("claim_evidence", "publication", "observed_measurement", "source_currentness")

    @model_validator(mode="after")
    def _limited_candidate(self) -> RegisteredDerivedInputEvaluation:
        if self.may_not_use_for != (
            "claim_evidence",
            "publication",
            "observed_measurement",
            "source_currentness",
        ):
            raise ValueError("composition_input_prohibited_uses_cannot_be_weakened")
        if self.status == "candidate" and (
            self.structural_correspondence != "recomputed"
            or self.value is None
            or not self.value.is_finite()
            or self.refusal_codes
            or "external_empirical_context_not_established" not in self.limitation_codes
            or "derivation_uncertainty_not_established" not in self.limitation_codes
        ):
            raise ValueError("composition_input_candidate_must_preserve_limitations")
        if self.status == "refused" and (not self.refusal_codes or self.value is not None):
            raise ValueError("composition_input_refusal_invalid")
        return self


def _same_ref(left: ArtifactRef | None, right: ArtifactRef | None) -> bool:
    return (None if left is None else artifact_ref_identity_key(left)) == (
        None if right is None else artifact_ref_identity_key(right)
    )


def verify_registered_derived_family(
    profile: RegisteredDerivedInputProfile, family: TransformFamily
) -> None:
    """Require the selected arithmetic ABI to implement this finite relation."""
    roles = {item.role for item in profile.inputs}
    expression = family.expression
    if (
        family.family_id != profile.family_id
        or family.method_version != profile.method_version
        or {item.role for item in family.input_specs} != roles
        or any("candidate_source" not in item.allowed_input_kinds for item in family.input_specs)
        or family.parameter_rules
        or family.output_parameter_bindings
        or expression.operator != "multiply"
        or len(expression.operands) != 2
        or {item.role for item in expression.operands} != roles
        or any(item.operator != "current_value" for item in expression.operands)
    ):
        raise ValueError("composition_input_registered_family_relation_mismatch")


def recompute_native_derivation_source_projection(
    *,
    profile_ref: RegisteredDerivedInputProfileRef,
    profile: RegisteredDerivedInputProfile,
    context_ref: RegisteredDerivedInputContextRef,
    context: RegisteredDerivedInputContext,
    role: str,
    occurrence_ref: ScopedMeasurementOccurrenceRef,
    occurrence: ScopedMeasurementOccurrence,
    replayed_occurrence: ScopedMeasurementOccurrence,
    source_selection: ScopedSourceSelection,
    definition: VariableSemanticDefinition,
    representation: VariableRepresentation,
    binding_profile: MeasurementBindingProfile,
) -> NativeDerivationSourceProjection:
    """Recompute the exact selected source point and declared semantic basis.

    Callers independently reopen native admission and source bytes first. This
    predicate proves correspondence to those selected declarations, not external
    truth or an institutional empirical authority score.
    """
    selected = tuple(item for item in profile.inputs if item.role == role)
    expected_occurrences = {item.role: item.occurrence_ref for item in context.roles}
    expected_scopes = {item.role: item.scope for item in context.role_scopes}
    if (
        len(selected) != 1
        or not _same_ref(context.profile_ref, profile_ref)
        or not _same_ref(expected_occurrences.get(role), occurrence_ref)
        or expected_scopes.get(role) != occurrence.source_scope
    ):
        raise ValueError("composition_input_native_role_context_mismatch")
    basis = selected[0].basis
    if (
        occurrence != replayed_occurrence
        or not _same_ref(
            source_selection.declared_source_definition_ref, basis.semantic_definition_ref
        )
        or not _same_ref(
            source_selection.declared_source_representation_ref, basis.representation_ref
        )
        or not _same_ref(representation.semantic_definition_ref, basis.semantic_definition_ref)
    ):
        raise ValueError("composition_input_native_source_basis_mismatch")
    if (
        occurrence.canonical_variable != source_selection.canonical_variable
        or occurrence.observation_class != "observed"
        or source_selection.observation_class != "observed"
        or source_selection.is_proxy
        or occurrence.aggregation_method != "identity"
        or len(occurrence.raw_values) != 1
        or occurrence.year != context.year
        or occurrence.survey_year is not None
        or occurrence.wave is not None
        or occurrence.canonical_unit != representation.unit_id
        or representation.quantity_kind != "flow"
        or representation.time_support != "period_total"
        or representation.temporal_granularity != "annual"
        or representation.aggregation != "identity"
        or representation.scale_to_unit != Decimal(1)
        or representation.population_ref != occurrence.source_scope.population_ref
        or not representation.grain
    ):
        raise ValueError("composition_input_native_annual_point_mismatch")
    if (
        binding_profile.schema_version != "polisyos.catalog.measurement_binding_profile.v3"
        or MeasurementAxis.MONEY_UNIT not in binding_profile.required_axes
        or any(
            getattr(representation, axis.value) is None for axis in binding_profile.required_axes
        )
    ):
        raise ValueError("composition_input_native_required_axis_unknown")
    money = representation.money_unit
    if (
        money is None
        or money.nominal_year is None
        or money.price_base is None
        or not money.price_base.strip()
        or money.price_base != money.price_base.strip()
    ):
        raise ValueError("composition_input_native_money_basis_not_established")
    scope = occurrence.source_scope
    if (
        scope.period_basis != "calendar_year"
        or scope.period_start != date(context.year, 1, 1)
        or scope.period_end != date(context.year, 12, 31)
        or scope.time_role != "observation_time"
    ):
        raise ValueError("composition_input_native_exact_calendar_year_required")
    return NativeDerivationSourceProjection(
        profile_ref=profile_ref,
        context_ref=context_ref,
        role=role,
        occurrence_ref=occurrence_ref,
        source_basis=basis,
        source_variable_id=occurrence.canonical_variable,
        year=context.year,
        canonical_value=Decimal(replayed_occurrence.canonical_value),
        unit_id=representation.unit_id,
    )


def evaluate_registered_derived_input_correspondence(
    *,
    correspondence: RegisteredDerivedInputCorrespondence,
    profile: RegisteredDerivedInputProfile,
    context: RegisteredDerivedInputContext,
    obligation_ref: ArtifactRef,
    obligation: ModelInputObligation,
    target_definition: VariableSemanticDefinition,
    target_representation: VariableRepresentation,
    binding_profile: MeasurementBindingProfile,
    units_registry: UnitsRegistry | None,
    recipe: CompositionRecipe,
    series: CompositionDerivedSeries,
    roles: tuple[ReplayedCandidateDerivationRole, ...],
) -> RegisteredDerivedInputEvaluation:
    """Join the registered relation, replayed sources and exact v3 output.

    The Core composition resolver supplies arithmetic replay; this predicate
    never evaluates an expression or converts a unit. It separately checks
    declared semantic coordinates and preserves the empirical-authority limit.
    """
    refusals: list[str] = []
    port = obligation.port
    if any(
        not _same_ref(left, right)
        for left, right in (
            (correspondence.model_input_obligation_ref, obligation_ref),
            (context.model_input_obligation_ref, obligation_ref),
            (correspondence.model_interface_ref, obligation.interface_ref),
            (context.model_interface_ref, obligation.interface_ref),
            (correspondence.profile_ref, context.profile_ref),
            (profile.output.semantic_definition_ref, port.semantic_definition_ref),
            (profile.output.representation_ref, port.representation_ref),
            (profile.output.binding_profile_ref, port.binding_profile_ref),
            (target_representation.semantic_definition_ref, port.semantic_definition_ref),
            (context.registry_bundle_ref, obligation.registry_bundle_ref),
        )
    ) or (
        correspondence.year != context.year
        or correspondence.model_port_id != port.port_id
        or context.model_port_id != port.port_id
        or context.output_scope != port.scope
    ):
        refusals.append("target_selection_mismatch")
    if (
        port.purpose != "simulation_input"
        or port.carrier != "method_input"
        or port.physical_encoding is None
        or port.physical_encoding.shape
    ):
        refusals.append("scalar_method_flow_port_required")
    if (
        target_representation.quantity_kind != "flow"
        or target_representation.measure_form != "absolute"
        or target_representation.time_support != "period_total"
        or target_representation.temporal_granularity != "annual"
        or target_representation.aggregation != "identity"
        or target_representation.scale_to_unit != Decimal(1)
        or target_representation.unit_id != port.unit_id
        or target_representation.numerator_ref is not None
        or target_representation.denominator_ref is not None
        or target_representation.population_ref != port.scope.population_ref
    ):
        refusals.append("target_annual_absolute_flow_required")
    if (
        binding_profile.schema_version != "polisyos.catalog.measurement_binding_profile.v3"
        or MeasurementAxis.MONEY_UNIT not in binding_profile.required_axes
        or MeasurementAxis.METHODOLOGY_REF in binding_profile.required_axes
        or any(
            getattr(target_representation, axis.value) is None
            for axis in binding_profile.required_axes
        )
    ):
        refusals.append("target_required_axis_not_established")
    expected_roles = tuple(item.role for item in profile.inputs)
    if (
        tuple(item.role for item in correspondence.roles) != expected_roles
        or tuple(item.selection for item in roles) != correspondence.roles
        or tuple(item.role for item in context.roles) != expected_roles
    ):
        refusals.append("complete_registered_role_set_required")
    by_role = {item.selection.role: item for item in roles}
    if set(by_role) != set(expected_roles):
        return RegisteredDerivedInputEvaluation(
            status="refused",
            structural_correspondence="not_established",
            refusal_codes=tuple(dict.fromkeys((*refusals, "exact_role_set_required"))),
        )
    for role in roles:
        label = role.selection.role
        try:
            expected_projection = recompute_native_derivation_source_projection(
                profile_ref=correspondence.profile_ref,
                profile=profile,
                context_ref=correspondence.context_ref,
                context=context,
                role=label,
                occurrence_ref=role.projection.occurrence_ref,
                occurrence=role.occurrence,
                replayed_occurrence=role.replayed_occurrence,
                source_selection=role.source_selection,
                definition=role.definition,
                representation=role.representation,
                binding_profile=role.binding_profile,
            )
            if expected_projection != role.projection:
                refusals.append(f"{label}_native_projection_mismatch")
        except ValueError as exc:
            refusals.append(f"{label}_{exc}")
        source = role.series
        if (
            not _same_ref(source.source_occurrence_ref, role.projection.occurrence_ref)
            or not _same_ref(source.source_ref, role.occurrence.source_record_ref)
            or not _same_ref(source.context_ref, correspondence.context_ref)
            or not _same_ref(source.scope_ref, correspondence.context_ref)
            or source.units_profile != "selected_registry_bundle"
            or not _same_ref(source.registry_bundle_ref, context.registry_bundle_ref)
            or source.observation_class != "candidate"
            or source.evidence_status != "not_established"
            or source.variable_id != role.projection.source_variable_id
            or source.basis.quantity_kind != role.projection.quantity_kind
            or source.basis.unit != role.projection.unit_id
            or len(source.points) != 1
            or source.points[0].year != context.year
            or source.points[0].value != role.projection.canonical_value
            or not any(
                _same_ref(ref, role.selection.source_projection_ref) for ref in source.lineage_refs
            )
            or role.representation.grain != target_representation.grain
        ):
            refusals.append(f"{label}_candidate_source_projection_mismatch")
    ratio = by_role[profile.ratio_role]
    denominator = by_role[profile.denominator_role]
    if (
        ratio.representation.measure_form != "ratio"
        or ratio.representation.unit_id != "ratio"
        or not _same_ref(ratio.representation.numerator_ref, port.semantic_definition_ref)
        or not _same_ref(
            ratio.representation.denominator_ref,
            denominator.projection.source_basis.semantic_definition_ref,
        )
    ):
        refusals.append("registered_ratio_role_semantics_mismatch")
    if (
        denominator.representation.measure_form != "absolute"
        or denominator.representation.unit_id != target_representation.unit_id
        or denominator.representation.numerator_ref is not None
        or denominator.representation.denominator_ref is not None
    ):
        refusals.append("registered_denominator_role_semantics_mismatch")
    money = target_representation.money_unit
    canonical_money = None if units_registry is None else units_registry.units.get(port.unit_id)
    if not isinstance(canonical_money, MoneyUnit) or money is None:
        refusals.append("canonical_money_unit_not_established")
    elif (
        money.currency != canonical_money.currency
        or (
            canonical_money.nominal_year is not None
            and money.nominal_year != canonical_money.nominal_year
        )
        or (
            canonical_money.price_base is not None
            and money.price_base != canonical_money.price_base
        )
    ):
        refusals.append("canonical_money_unit_mismatch")
    if (
        money is None
        or money.nominal_year is None
        or money.price_base is None
        or not money.price_base.strip()
        or money.price_base != money.price_base.strip()
        or ratio.representation.money_unit != money
        or denominator.representation.money_unit != money
    ):
        refusals.append("money_basis_not_established")
    scopes = (port.scope, *(item.occurrence.source_scope for item in roles))
    if any(
        scope.period_basis != "calendar_year"
        or scope.period_start != date(context.year, 1, 1)
        or scope.period_end != date(context.year, 12, 31)
        or scope.time_role != "observation_time"
        or (scope.geography_ref, scope.jurisdiction_ref)
        != (port.scope.geography_ref, port.scope.jurisdiction_ref)
        for scope in scopes
    ):
        refusals.append("exact_role_geography_calendar_scope_required")
    if ratio.occurrence.source_scope.population_ref != port.scope.population_ref:
        refusals.append("numerator_population_scope_mismatch")
    try:
        verify_registered_derived_family(profile, recipe.family)
    except ValueError as exc:
        refusals.append(str(exc))
    if (
        not _same_ref(
            profile.registry_ref,
            ArtifactRef(
                artifact_id=recipe.registry_artifact.artifact_id,
                kind=recipe.registry_artifact.kind,
                media_type=recipe.registry_artifact.media_type,
                manifest_profile_sha256=recipe.registry_artifact.manifest_profile_sha256,
            ),
        )
        or not _same_ref(recipe.context.context_ref, correspondence.context_ref)
        or not _same_ref(recipe.context.scope_ref, correspondence.context_ref)
        or not _same_ref(recipe.context.registry_bundle_ref, context.registry_bundle_ref)
        or recipe.context.years != (context.year,)
        or recipe.parameters
        or any(item.kind != "candidate_source" for item in recipe.inputs)
        or {item.role for item in recipe.inputs} != set(expected_roles)
        or any(
            item.artifact.artifact_id != by_role[item.role].selection.source_series_ref.artifact_id
            or item.artifact.manifest_profile_sha256
            != by_role[item.role].selection.source_series_ref.manifest_profile_sha256
            for item in recipe.inputs
            if item.role in by_role
        )
    ):
        refusals.append("selected_recipe_context_or_roles_mismatch")
    if (
        recipe.output_basis.quantity_kind != target_representation.quantity_kind
        or recipe.output_basis.unit != target_representation.unit_id
        or series.variable_id != recipe.output_variable_id
        or series.recipe_id != recipe.recipe_id
        or series.context != recipe.context
        or series.observation_class != "derived"
        or series.evidence_status != "not_established"
        or series.effective_score is not None
        or series.basis != recipe.output_basis
        or len(series.points) != 1
        or series.points[0].year != context.year
    ):
        refusals.append("derived_output_semantics_mismatch")
    if refusals:
        return RegisteredDerivedInputEvaluation(
            status="refused",
            structural_correspondence="not_established",
            refusal_codes=tuple(dict.fromkeys(refusals)),
        )
    return RegisteredDerivedInputEvaluation(
        status="candidate",
        structural_correspondence="recomputed",
        value=series.points[0].value,
        limitation_codes=tuple(
            dict.fromkeys(
                (
                    *series.limitations,
                    "external_empirical_context_not_established",
                    "derivation_uncertainty_not_established",
                    "source_currentness_not_established",
                )
            )
        ),
    )


def persist_registered_derived_input_profile(
    store: ArtifactStore, profile: RegisteredDerivedInputProfile
) -> RegisteredDerivedInputProfileRef:
    """Persist one exact selected operator registration and semantic role map."""
    return RegisteredDerivedInputProfileRef.model_validate(
        _persist(store, profile).model_dump(mode="python")
    )


def load_registered_derived_input_profile(
    store: CoreJSONArtifactStore, ref: RegisteredDerivedInputProfileRef
) -> RegisteredDerivedInputProfile:
    """Reopen the registered profile with its complete selected dependencies."""
    result = validate_core_model_json_artifact(RegisteredDerivedInputProfile, store, ref)
    result.require_lineage(store.get_manifest(ref))
    return result


def persist_registered_derived_input_context(
    store: ArtifactStore, context: RegisteredDerivedInputContext
) -> RegisteredDerivedInputContextRef:
    """Persist candidate target and role-specific scopes without empirical promotion."""
    return RegisteredDerivedInputContextRef.model_validate(
        _persist(store, context).model_dump(mode="python")
    )


def load_registered_derived_input_context(
    store: CoreJSONArtifactStore, ref: RegisteredDerivedInputContextRef
) -> RegisteredDerivedInputContext:
    """Reopen every exact target and role-occurrence edge in the selected context."""
    result = validate_core_model_json_artifact(RegisteredDerivedInputContext, store, ref)
    result.require_lineage(store.get_manifest(ref))
    return result


def persist_native_derivation_source_projection(
    store: ArtifactStore, projection: NativeDerivationSourceProjection
) -> NativeDerivationSourceProjectionRef:
    """Persist a recomputed projection; consumers independently replay its inputs."""
    return NativeDerivationSourceProjectionRef.model_validate(
        _persist(store, projection).model_dump(mode="python")
    )


def load_native_derivation_source_projection(
    store: CoreJSONArtifactStore, ref: NativeDerivationSourceProjectionRef
) -> NativeDerivationSourceProjection:
    """Reopen the selected projection and exact source/basis dependencies."""
    result = validate_core_model_json_artifact(NativeDerivationSourceProjection, store, ref)
    result.require_lineage(store.get_manifest(ref))
    return result


def persist_registered_derived_input_correspondence(
    store: ArtifactStore, correspondence: RegisteredDerivedInputCorrespondence
) -> DerivedInputCorrespondenceRef:
    """Persist the complete selected v3 recipe, source and target correspondence."""
    return DerivedInputCorrespondenceRef.model_validate(
        _persist(store, correspondence).model_dump(mode="python")
    )


def load_registered_derived_input_correspondence(
    store: CoreJSONArtifactStore, ref: DerivedInputCorrespondenceRef
) -> RegisteredDerivedInputCorrespondence:
    """Reopen all exact selected semantic and arithmetic correspondence edges."""
    result = validate_core_model_json_artifact(RegisteredDerivedInputCorrespondence, store, ref)
    result.require_lineage(store.get_manifest(ref))
    return result


def _persist(
    store: ArtifactStore,
    value: RegisteredDerivedInputProfile
    | RegisteredDerivedInputContext
    | NativeDerivationSourceProjection
    | RegisteredDerivedInputCorrespondence,
) -> ArtifactRef:
    return store.put_json(
        value,
        PutOptions(
            kind=value.ARTIFACT_KIND,
            media_type=value.ARTIFACT_MEDIA_TYPE,
            producer=ProducerInfo(
                component="polisyos.core.contracts.semantic_composition_binding", version="1.0.0"
            ),
            schema=SchemaInfo(
                name=value.ARTIFACT_SCHEMA_NAME, version=value.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=value.lineage_inputs(),
        ),
        return_selected_profile=True,
    )
