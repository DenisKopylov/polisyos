"""Bounded candidate semantics for a ratio times its selected denominator.

The arithmetic certificate and independently replayed source rows establish
different predicates from an external provider's empirical denominator context.
This first profile supports an explicit fixture declaration of that context;
it never turns the declaration into scientific or publication authority.
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
    PutOptions,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef
from polisyos.ir.kernel import MoneyUnit, UnitsRegistry

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
    from polisyos.core.derivations import DerivationRecipe, DerivedSeries, SourceSeries

    from .model_input_requirements import ModelInputObligation


class _DerivedContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    def lineage_inputs(self) -> list[InputRef]:
        """Return the complete selected dependency edges in contract order."""
        return []

    def require_lineage(self, manifest: ArtifactManifest) -> None:
        """Reject omitted, substituted, or additional selected dependency edges."""
        if manifest.inputs != self.lineage_inputs():
            raise ValueError("derived_input_semantic_lineage_mismatch")


class DerivedInputProfileRef(SelectedVariableBindingRef):
    """Exact selected version of the bounded semantic operator profile."""

    kind: Literal["catalog.derived_input_profile"] = "catalog.derived_input_profile"
    media_type: Literal["application/json"] = "application/json"


class RatioDenominatorSourceContextRef(SelectedVariableBindingRef):
    """Exact declared source context for the ratio's denominator release."""

    kind: Literal["catalog.ratio_denominator_source_context"] = (
        "catalog.ratio_denominator_source_context"
    )
    media_type: Literal["application/json"] = "application/json"


class DerivedInputCorrespondenceRef(SelectedVariableBindingRef):
    """Exact bounded correspondence basis reopened by the actual consumer."""

    kind: Literal["catalog.derived_input_correspondence"] = "catalog.derived_input_correspondence"
    media_type: Literal["application/json"] = "application/json"


class DerivedInputProfile(_DerivedContract):
    """One closed annual-flow operator, with explicit physical value packing."""

    ARTIFACT_KIND: ClassVar[str] = "catalog.derived_input_profile"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.catalog.DerivedInputProfile"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    schema_version: Literal["1.0"] = "1.0"
    profile_id: Literal["ratio_times_denominator.calendar_year_flow.v1"] = (
        "ratio_times_denominator.calendar_year_flow.v1"
    )
    operator: Literal["ratio_times_denominator"] = "ratio_times_denominator"
    output_projection: Literal["scalar", "singleton_vector"] = "scalar"
    authority_purpose: Literal["candidate_simulation_input_only"] = (
        "candidate_simulation_input_only"
    )
    source_context_scope: Literal["bounded_fixture_declaration"] = "bounded_fixture_declaration"
    uncertainty_status: Literal["not_established"] = "not_established"


class RatioDenominatorSourceContext(_DerivedContract):
    """Fixture producer's explicit context, separate from verified arithmetic.

    Exact occurrence refs distinguish releases even when their numeric values
    coincide. This declaration proves neither a real provider's methodology nor
    an external empirical relationship between the two measurements.
    """

    ARTIFACT_KIND: ClassVar[str] = "catalog.ratio_denominator_source_context"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.catalog.RatioDenominatorSourceContext"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    schema_version: Literal["1.0"] = "1.0"
    declaration_scope: Literal["bounded_fixture_declaration"] = "bounded_fixture_declaration"
    authority_purpose: Literal["candidate_simulation_input_only"] = (
        "candidate_simulation_input_only"
    )
    predicate_provenance: Literal["institutionally_supplied"] = "institutionally_supplied"
    scope_note: str = Field(min_length=1, max_length=2000)
    ratio_occurrence_ref: ScopedMeasurementOccurrenceRef
    ratio_definition_ref: VariableSemanticDefinitionRef
    ratio_representation_ref: VariableRepresentationRef
    denominator_occurrence_ref: ScopedMeasurementOccurrenceRef
    denominator_definition_ref: VariableSemanticDefinitionRef
    denominator_representation_ref: VariableRepresentationRef
    money_unit: MoneyUnit

    def lineage_inputs(self) -> list[InputRef]:
        """Bind the producer declaration to exact role-qualified selected inputs."""
        return [
            input_ref_from_artifact_ref(ref, role=role)
            for role, ref in (
                ("ratio.occurrence", self.ratio_occurrence_ref),
                ("ratio.definition", self.ratio_definition_ref),
                ("ratio.representation", self.ratio_representation_ref),
                ("denominator.occurrence", self.denominator_occurrence_ref),
                ("denominator.definition", self.denominator_definition_ref),
                ("denominator.representation", self.denominator_representation_ref),
            )
        ]


class DerivedMeasurementRole(_DerivedContract):
    """One source series joined to the independently replayable admitted row."""

    role: Literal["denominator", "ratio"]
    source_series_ref: SelectedVariableBindingRef
    occurrence_ref: ScopedMeasurementOccurrenceRef
    definition_ref: VariableSemanticDefinitionRef
    representation_ref: VariableRepresentationRef

    @model_validator(mode="after")
    def _source_series_kind(self) -> DerivedMeasurementRole:
        if (
            self.source_series_ref.kind != "polisyos.runtime.derivation_source_series"
            or self.source_series_ref.media_type != "application/json"
        ):
            raise ValueError("derived_input_source_series_kind_mismatch")
        return self

    def lineage_inputs(self) -> list[InputRef]:
        """Return the exact evidence and arithmetic source for this role."""
        return [
            input_ref_from_artifact_ref(ref, role=f"{self.role}.{suffix}")
            for suffix, ref in (
                ("source_series", self.source_series_ref),
                ("occurrence", self.occurrence_ref),
                ("definition", self.definition_ref),
                ("representation", self.representation_ref),
            )
        ]


class DerivedInputCorrespondenceBasis(_DerivedContract):
    """Content-bound selection for one derived output and one model port."""

    ARTIFACT_KIND: ClassVar[str] = "catalog.derived_input_correspondence"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.catalog.DerivedInputCorrespondenceBasis"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    schema_version: Literal["1.0"] = "1.0"
    authority_purpose: Literal["candidate_simulation_input_only"] = (
        "candidate_simulation_input_only"
    )
    profile_ref: DerivedInputProfileRef
    source_context_ref: RatioDenominatorSourceContextRef
    model_input_obligation_ref: SelectedVariableBindingRef
    model_interface_ref: SelectedVariableBindingRef
    model_port_id: str = Field(min_length=1)
    target_definition_ref: VariableSemanticDefinitionRef
    target_representation_ref: VariableRepresentationRef
    binding_profile_ref: MeasurementBindingProfileRef
    scope: ModelInputScope
    year: int = Field(ge=1900, le=2200, strict=True)
    registry_ref: SelectedVariableBindingRef
    family_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    recipe_ref: SelectedVariableBindingRef
    certificate_ref: SelectedVariableBindingRef
    output_ref: SelectedVariableBindingRef
    roles: tuple[DerivedMeasurementRole, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def _selected_kinds_and_roles(self) -> DerivedInputCorrespondenceBasis:
        for ref, kind in (
            (self.model_input_obligation_ref, "runtime.quality.model_input_obligation"),
            (self.model_interface_ref, "runtime.quality.program_graph_input_interface"),
            (self.registry_ref, "polisyos.runtime.transform_family_registry"),
            (self.recipe_ref, "polisyos.runtime.derivation_recipe"),
            (self.certificate_ref, "polisyos.runtime.derivation_certificate"),
            (self.output_ref, "polisyos.runtime.derived_economic_series"),
        ):
            if ref.kind != kind or ref.media_type != "application/json":
                raise ValueError("derived_input_selected_kind_mismatch")
        if tuple(item.role for item in self.roles) != ("denominator", "ratio"):
            raise ValueError("derived_input_exact_role_set_required")
        return self

    def lineage_inputs(self) -> list[InputRef]:
        """Return all selected target, operator, context and role evidence edges."""
        inputs = [
            input_ref_from_artifact_ref(ref, role=role)
            for role, ref in (
                ("semantic_profile", self.profile_ref),
                ("source_context", self.source_context_ref),
                ("target.obligation", self.model_input_obligation_ref),
                ("target.interface", self.model_interface_ref),
                ("target.definition", self.target_definition_ref),
                ("target.representation", self.target_representation_ref),
                ("target.binding_profile", self.binding_profile_ref),
                ("derivation.registry", self.registry_ref),
                ("derivation.recipe", self.recipe_ref),
                ("derivation.certificate", self.certificate_ref),
                ("derivation.output", self.output_ref),
            )
        ]
        for role in self.roles:
            inputs.extend(role.lineage_inputs())
        return inputs


class DerivedInputEvaluation(_DerivedContract):
    """Candidate numerical use, without an empirical correspondence claim."""

    status: Literal["candidate", "refused"]
    structural_correspondence: Literal["recomputed", "not_established"]
    empirical_context: Literal["institutionally_supplied"] = "institutionally_supplied"
    uncertainty_status: Literal["not_established"] = "not_established"
    authority_purpose: Literal["candidate_simulation_input_only"] = (
        "candidate_simulation_input_only"
    )
    may_not_use_for: tuple[
        Literal["claim_evidence", "publication", "observed_measurement", "source_currentness"], ...
    ] = ("claim_evidence", "publication", "observed_measurement", "source_currentness")
    value: Decimal | None = None
    limitation_codes: tuple[str, ...] = ()
    refusal_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _candidate_is_limited(self) -> DerivedInputEvaluation:
        if self.may_not_use_for != (
            "claim_evidence",
            "publication",
            "observed_measurement",
            "source_currentness",
        ):
            raise ValueError("derived_input_prohibited_uses_cannot_be_weakened")
        if self.status == "candidate" and (
            self.structural_correspondence != "recomputed"
            or self.value is None
            or not self.value.is_finite()
            or self.refusal_codes
            or "external_empirical_context_not_established" not in self.limitation_codes
            or "derivation_uncertainty_not_established" not in self.limitation_codes
        ):
            raise ValueError("derived_input_candidate_must_preserve_limitations")
        if self.status == "refused" and (not self.refusal_codes or self.value is not None):
            raise ValueError("derived_input_refusal_invalid")
        return self


@dataclass(frozen=True)
class ReplayedDerivedMeasurementRole:
    """Owner-loaded role evidence supplied to the pure Core correspondence rule."""

    selection: DerivedMeasurementRole
    occurrence: ScopedMeasurementOccurrence
    replayed_occurrence: ScopedMeasurementOccurrence
    source_selection: ScopedSourceSelection
    definition: VariableSemanticDefinition
    representation: VariableRepresentation
    series: SourceSeries


def _same_ref(left: ArtifactRef | None, right: ArtifactRef | None) -> bool:
    return (None if left is None else artifact_ref_identity_key(left)) == (
        None if right is None else artifact_ref_identity_key(right)
    )


def evaluate_derived_input_correspondence(
    *,
    basis: DerivedInputCorrespondenceBasis,
    profile: DerivedInputProfile,
    source_context: RatioDenominatorSourceContext,
    obligation_ref: ArtifactRef,
    obligation: ModelInputObligation,
    target_definition: VariableSemanticDefinition,
    target_representation: VariableRepresentation,
    binding_profile: MeasurementBindingProfile,
    units_registry: UnitsRegistry | None,
    recipe: DerivationRecipe,
    series: DerivedSeries,
    roles: tuple[ReplayedDerivedMeasurementRole, ...],
) -> DerivedInputEvaluation:
    """Recompute exact typed joins for the closed ratio-times-denominator rule.

    Callers reopen every selected artifact, independently replay admitted source
    rows, and resolve the certified arithmetic first. This function validates
    their composition, rather than applying the same-definition measurement
    evaluator to an output that is explicitly derived.
    """
    refusals: list[str] = []
    port = obligation.port
    if any(
        not _same_ref(left, right)
        for left, right in (
            (basis.model_input_obligation_ref, obligation_ref),
            (basis.model_interface_ref, obligation.interface_ref),
            (basis.target_definition_ref, port.semantic_definition_ref),
            (basis.target_representation_ref, port.representation_ref),
            (basis.binding_profile_ref, port.binding_profile_ref),
            (target_representation.semantic_definition_ref, port.semantic_definition_ref),
        )
    ) or (basis.model_port_id, basis.scope) != (port.port_id, port.scope):
        refusals.append("target_selection_mismatch")
    if port.purpose != "simulation_input":
        refusals.append("annual_flow_simulation_port_required")
    expected_shape = () if profile.output_projection == "scalar" else (1,)
    if port.physical_encoding is None or port.physical_encoding.shape != expected_shape:
        refusals.append("declared_output_shape_required")
    if (
        target_representation.quantity_kind != "flow"
        or target_representation.measure_form != "absolute"
        or target_representation.time_support != "period_total"
        or target_representation.temporal_granularity != "annual"
        or target_representation.aggregation != "identity"
        or target_representation.scale_to_unit != Decimal("1")
        or target_representation.unit_id != port.unit_id
        or target_representation.numerator_ref is not None
        or target_representation.denominator_ref is not None
    ):
        refusals.append("target_annual_absolute_flow_required")
    if (
        binding_profile.schema_version != "polisyos.catalog.measurement_binding_profile.v3"
        or MeasurementAxis.MONEY_UNIT not in binding_profile.required_axes
    ):
        refusals.append("money_basis_axis_must_be_required")
    for axis in binding_profile.required_axes:
        if getattr(target_representation, axis.value) is None:
            refusals.append(f"target_required_axis_unknown:{axis.value}")
        if axis == MeasurementAxis.METHODOLOGY_REF:
            refusals.append("output_methodology_correspondence_not_established")
    if (
        source_context.declaration_scope != profile.source_context_scope
        or tuple(item.selection.role for item in roles) != ("denominator", "ratio")
        or tuple(item.selection for item in roles) != basis.roles
    ):
        refusals.append("exact_role_context_required")
    by_role = {item.selection.role: item for item in roles}
    if set(by_role) != {"denominator", "ratio"}:
        return DerivedInputEvaluation(
            status="refused",
            structural_correspondence="not_established",
            refusal_codes=tuple(dict.fromkeys((*refusals, "exact_role_set_required"))),
        )
    ratio, denominator = by_role["ratio"], by_role["denominator"]
    for role, expected_occurrence, expected_definition, expected_representation in (
        (
            ratio,
            source_context.ratio_occurrence_ref,
            source_context.ratio_definition_ref,
            source_context.ratio_representation_ref,
        ),
        (
            denominator,
            source_context.denominator_occurrence_ref,
            source_context.denominator_definition_ref,
            source_context.denominator_representation_ref,
        ),
    ):
        selected = role.selection
        label = selected.role
        occurrence = role.occurrence
        source = role.source_selection
        representation = role.representation
        if any(
            not _same_ref(left, right)
            for left, right in (
                (selected.occurrence_ref, expected_occurrence),
                (selected.definition_ref, expected_definition),
                (selected.representation_ref, expected_representation),
            )
        ):
            refusals.append(f"{label}_source_context_mismatch")
        if occurrence != role.replayed_occurrence:
            refusals.append(f"{label}_source_point_replay_mismatch")
        if (
            not _same_ref(source.declared_source_definition_ref, selected.definition_ref)
            or not _same_ref(source.declared_source_representation_ref, selected.representation_ref)
            or not _same_ref(representation.semantic_definition_ref, selected.definition_ref)
        ):
            refusals.append(f"{label}_source_declared_semantics_mismatch")
        if (
            occurrence.observation_class != "observed"
            or source.observation_class != "observed"
            or source.is_proxy
            or occurrence.aggregation_method != "identity"
            or len(occurrence.raw_values) != 1
        ):
            refusals.append(f"{label}_exact_observed_point_required")
        semantic_id = f"{role.definition.namespace}.{role.definition.stable_id}"
        if (
            occurrence.canonical_variable != semantic_id
            or source.canonical_variable != semantic_id
            or role.series.variable_id != semantic_id
            or role.series.observation_class != occurrence.observation_class
            or role.series.basis.quantity_kind != representation.quantity_kind
            or role.series.basis.unit != representation.unit_id
            or occurrence.canonical_unit != representation.unit_id
        ):
            refusals.append(f"{label}_series_semantics_mismatch")
        if (
            len(role.series.points) != 1
            or role.series.points[0].year != basis.year
            or role.series.points[0].value != Decimal(role.replayed_occurrence.canonical_value)
            or occurrence.year != basis.year
            or occurrence.survey_year is not None
            or occurrence.wave is not None
        ):
            refusals.append(f"{label}_series_point_mismatch")
        if (
            representation.quantity_kind != "flow"
            or representation.time_support != "period_total"
            or representation.temporal_granularity != "annual"
            or representation.aggregation != "identity"
            or representation.scale_to_unit != Decimal("1")
            or representation.population_ref != occurrence.source_scope.population_ref
            or not representation.grain
            or representation.grain != target_representation.grain
        ):
            refusals.append(f"{label}_annual_flow_representation_required")
    if (
        ratio.representation.measure_form != "ratio"
        or ratio.representation.unit_id != "ratio"
        or not _same_ref(ratio.representation.numerator_ref, basis.target_definition_ref)
    ):
        refusals.append("ratio_numerator_target_mismatch")
    if not _same_ref(ratio.representation.denominator_ref, denominator.selection.definition_ref):
        refusals.append("ratio_denominator_definition_mismatch")
    if (
        denominator.representation.measure_form != "absolute"
        or denominator.representation.numerator_ref is not None
        or denominator.representation.denominator_ref is not None
        or denominator.representation.unit_id != target_representation.unit_id
    ):
        refusals.append("absolute_denominator_required")
    money = target_representation.money_unit
    canonical_money = None if units_registry is None else units_registry.units.get(port.unit_id)
    if not isinstance(canonical_money, MoneyUnit):
        refusals.append("canonical_money_unit_not_established")
    elif money is not None and (
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
    ):
        refusals.append("money_price_base_not_established")
    if any(
        candidate != money
        for candidate in (
            ratio.representation.money_unit,
            denominator.representation.money_unit,
            source_context.money_unit,
        )
    ):
        refusals.append("money_basis_mismatch")
    scopes = (ratio.occurrence.source_scope, denominator.occurrence.source_scope, port.scope)
    if any(
        scope.period_basis != "calendar_year"
        or scope.period_start != date(basis.year, 1, 1)
        or scope.period_end != date(basis.year, 12, 31)
        or scope.time_role != "observation_time"
        for scope in scopes
    ):
        refusals.append("exact_calendar_year_scope_required")
    # Population is role-specific: a government numerator and an economy-wide
    # denominator are legitimate. Shared geography and period are still required.
    if any(
        (scope.geography_ref, scope.jurisdiction_ref)
        != (port.scope.geography_ref, port.scope.jurisdiction_ref)
        for scope in scopes
    ):
        refusals.append("role_geography_scope_mismatch")
    if (
        ratio.occurrence.source_scope.population_ref != port.scope.population_ref
        or target_representation.population_ref != port.scope.population_ref
    ):
        refusals.append("numerator_population_scope_mismatch")
    expression = recipe.family.expression
    if (
        recipe.family.family_id != basis.family_id
        or recipe.method_version != basis.method_version
        or recipe.family.year_domain_role != "ratio"
        or recipe.parameters
        or recipe.family.parameter_rules
        or recipe.family.output_parameter_bindings
        or expression.operator != "multiply"
        or len(expression.operands) != 2
        or {item.role for item in expression.operands} != {"ratio", "denominator"}
        or any(item.operator != "current_value" for item in expression.operands)
    ):
        refusals.append("closed_ratio_times_denominator_operator_required")
    recipe_roles = {item.role: item for item in recipe.inputs}
    if set(recipe_roles) != set(by_role) or any(
        item.artifact.artifact_id != by_role[role].selection.source_series_ref.artifact_id
        or item.artifact.manifest_profile_sha256
        != by_role[role].selection.source_series_ref.manifest_profile_sha256
        for role, item in recipe_roles.items()
        if role in by_role
    ):
        refusals.append("recipe_role_source_mismatch")
    if (
        recipe.registry_artifact.artifact_id != basis.registry_ref.artifact_id
        or recipe.registry_artifact.manifest_profile_sha256
        != basis.registry_ref.manifest_profile_sha256
        or recipe.output_variable_id
        != f"{target_definition.namespace}.{target_definition.stable_id}"
        or series.variable_id != recipe.output_variable_id
        or series.recipe_id != recipe.recipe_id
        or series.observation_class != "derived"
        or series.basis.quantity_kind != target_representation.quantity_kind
        or series.basis.unit != target_representation.unit_id
        or len(series.points) != 1
        or series.points[0].year != basis.year
    ):
        refusals.append("derived_output_semantics_mismatch")
    if refusals:
        return DerivedInputEvaluation(
            status="refused",
            structural_correspondence="not_established",
            refusal_codes=tuple(dict.fromkeys(refusals)),
        )
    return DerivedInputEvaluation(
        status="candidate",
        structural_correspondence="recomputed",
        value=series.points[0].value,
        limitation_codes=(
            "bounded_fixture_semantics_declared",
            "external_empirical_context_not_established",
            "source_currentness_not_established",
            "derivation_uncertainty_not_established",
        ),
    )


def persist_derived_input_profile(
    store: ArtifactStore, value: DerivedInputProfile
) -> DerivedInputProfileRef:
    """Persist the selected closed candidate operator profile."""
    return DerivedInputProfileRef.model_validate(_persist(store, value).model_dump(mode="python"))


def persist_ratio_denominator_source_context(
    store: ArtifactStore, value: RatioDenominatorSourceContext
) -> RatioDenominatorSourceContextRef:
    """Persist the explicitly limited fixture source-context declaration."""
    return RatioDenominatorSourceContextRef.model_validate(
        _persist(store, value).model_dump(mode="python")
    )


def persist_derived_input_correspondence(
    store: ArtifactStore, value: DerivedInputCorrespondenceBasis
) -> DerivedInputCorrespondenceRef:
    """Persist exact candidate target, arithmetic and semantic evidence refs."""
    return DerivedInputCorrespondenceRef.model_validate(
        _persist(store, value).model_dump(mode="python")
    )


def _persist(
    store: ArtifactStore,
    value: DerivedInputProfile | RatioDenominatorSourceContext | DerivedInputCorrespondenceBasis,
) -> ArtifactRef:
    return store.put_json(
        value,
        PutOptions(
            kind=value.ARTIFACT_KIND,
            media_type=value.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=value.ARTIFACT_SCHEMA_NAME, version=value.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=value.lineage_inputs(),
        ),
        return_selected_profile=True,
    )


def load_derived_input_profile(
    store: CoreJSONArtifactStore, ref: DerivedInputProfileRef
) -> DerivedInputProfile:
    """Reopen the selected profile and require its exact dependency view."""
    value = validate_core_model_json_artifact(DerivedInputProfile, store, ref)
    value.require_lineage(store.get_manifest(ref))
    return value


def load_ratio_denominator_source_context(
    store: CoreJSONArtifactStore, ref: RatioDenominatorSourceContextRef
) -> RatioDenominatorSourceContext:
    """Reopen the exact selected fixture declaration without promoting it."""
    value = validate_core_model_json_artifact(RatioDenominatorSourceContext, store, ref)
    value.require_lineage(store.get_manifest(ref))
    return value


def load_derived_input_correspondence(
    store: CoreJSONArtifactStore, ref: DerivedInputCorrespondenceRef
) -> DerivedInputCorrespondenceBasis:
    """Reopen all selected basis bytes and the complete role-qualified edge set."""
    value = validate_core_model_json_artifact(DerivedInputCorrespondenceBasis, store, ref)
    value.require_lineage(store.get_manifest(ref))
    return value
