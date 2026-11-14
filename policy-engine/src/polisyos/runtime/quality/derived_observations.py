"""Runtime epoch recompute and compatibility surface for certified derivations.

Generic derivation contracts and replay are owned by :mod:`polisyos.core.derivations`.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Literal, Never, Self

from pydantic import Field, model_validator

from polisyos.core import artifacts
from polisyos.core.derivations import (
    _CANON_SPEC as _CANON_SPEC,
)
from polisyos.core.derivations import (
    _CERTIFICATE_SCHEMA as _CERTIFICATE_SCHEMA,
)
from polisyos.core.derivations import (
    _CERTIFICATE_SELECTED_VIEW_SCHEMA as _CERTIFICATE_SELECTED_VIEW_SCHEMA,
)
from polisyos.core.derivations import (
    _DEFAULT_UNITS_REGISTRY as _DEFAULT_UNITS_REGISTRY,
)
from polisyos.core.derivations import (
    _DERIVATION_PRODUCER as _DERIVATION_PRODUCER,
)
from polisyos.core.derivations import (
    _DERIVATION_RECIPE_SCHEMA as _DERIVATION_RECIPE_SCHEMA,
)
from polisyos.core.derivations import (
    _DERIVATION_RECIPE_SELECTED_VIEW_SCHEMA as _DERIVATION_RECIPE_SELECTED_VIEW_SCHEMA,
)
from polisyos.core.derivations import (
    _DERIVED_SERIES_SCHEMA as _DERIVED_SERIES_SCHEMA,
)
from polisyos.core.derivations import (
    _DERIVED_SERIES_SELECTED_VIEW_SCHEMA as _DERIVED_SERIES_SELECTED_VIEW_SCHEMA,
)
from polisyos.core.derivations import (
    _SOURCE_SERIES_PRODUCER as _SOURCE_SERIES_PRODUCER,
)
from polisyos.core.derivations import (
    _SOURCE_SERIES_SCHEMA as _SOURCE_SERIES_SCHEMA,
)
from polisyos.core.derivations import (
    _TRANSFORM_FAMILY_REGISTRY_SCHEMA as _TRANSFORM_FAMILY_REGISTRY_SCHEMA,
)
from polisyos.core.derivations import (
    CANDIDATE_SOURCE_SERIES_KIND as CANDIDATE_SOURCE_SERIES_KIND,
)
from polisyos.core.derivations import (
    COMPOSITION_DERIVATION_SCHEMA_VERSION as COMPOSITION_DERIVATION_SCHEMA_VERSION,
)
from polisyos.core.derivations import (
    DERIVATION_CERTIFICATE_KIND as DERIVATION_CERTIFICATE_KIND,
)
from polisyos.core.derivations import (
    DERIVATION_RECIPE_KIND as DERIVATION_RECIPE_KIND,
)
from polisyos.core.derivations import (
    DERIVATION_SCHEMA_VERSION as DERIVATION_SCHEMA_VERSION,
)
from polisyos.core.derivations import (
    DERIVED_SERIES_KIND as DERIVED_SERIES_KIND,
)
from polisyos.core.derivations import (
    ECONOMIC_SERIES_KIND as ECONOMIC_SERIES_KIND,
)
from polisyos.core.derivations import (
    LEGACY_DERIVATION_SCHEMA_VERSION as LEGACY_DERIVATION_SCHEMA_VERSION,
)
from polisyos.core.derivations import (
    PRICE_INDEX_SERIES_KIND as PRICE_INDEX_SERIES_KIND,
)
from polisyos.core.derivations import (
    SELECTED_VIEW_DERIVATION_SCHEMA_VERSION as SELECTED_VIEW_DERIVATION_SCHEMA_VERSION,
)
from polisyos.core.derivations import (
    SOURCE_SERIES_KIND as SOURCE_SERIES_KIND,
)
from polisyos.core.derivations import (
    TRANSFORM_FAMILY_REGISTRY_KIND as TRANSFORM_FAMILY_REGISTRY_KIND,
)
from polisyos.core.derivations import (
    ArithmeticExpression as ArithmeticExpression,
)
from polisyos.core.derivations import (
    ArithmeticOperator as ArithmeticOperator,
)
from polisyos.core.derivations import (
    ArtifactContractProjection as ArtifactContractProjection,
)
from polisyos.core.derivations import (
    ArtifactInputEdge as ArtifactInputEdge,
)
from polisyos.core.derivations import (
    AssumptionRule as AssumptionRule,
)
from polisyos.core.derivations import (
    AuthorityProjection as AuthorityProjection,
)
from polisyos.core.derivations import (
    AuthorityScore as AuthorityScore,
)
from polisyos.core.derivations import (
    BasisAttribute as BasisAttribute,
)
from polisyos.core.derivations import (
    BasisParameterBinding as BasisParameterBinding,
)
from polisyos.core.derivations import (
    BasisSignature as BasisSignature,
)
from polisyos.core.derivations import (
    CandidateDerivationInput as CandidateDerivationInput,
)
from polisyos.core.derivations import (
    CandidateSourceSeries as CandidateSourceSeries,
)
from polisyos.core.derivations import (
    CertificateInputAuthority as CertificateInputAuthority,
)
from polisyos.core.derivations import (
    CertifiedDerivationConsumption as CertifiedDerivationConsumption,
)
from polisyos.core.derivations import (
    CertifiedDerivedInput as CertifiedDerivedInput,
)
from polisyos.core.derivations import (
    CompositionCertificate as CompositionCertificate,
)
from polisyos.core.derivations import (
    CompositionDerivedSeries as CompositionDerivedSeries,
)
from polisyos.core.derivations import (
    CompositionMaterialization as CompositionMaterialization,
)
from polisyos.core.derivations import (
    CompositionRecipe as CompositionRecipe,
)
from polisyos.core.derivations import (
    CompositionRecipeInput as CompositionRecipeInput,
)
from polisyos.core.derivations import (
    CompositionResolution as CompositionResolution,
)
from polisyos.core.derivations import (
    DerivationCertificate as DerivationCertificate,
)
from polisyos.core.derivations import (
    DerivationContext as DerivationContext,
)
from polisyos.core.derivations import (
    DerivationDagInput as DerivationDagInput,
)
from polisyos.core.derivations import (
    DerivationDagMaterialization as DerivationDagMaterialization,
)
from polisyos.core.derivations import (
    DerivationDagNode as DerivationDagNode,
)
from polisyos.core.derivations import (
    DerivationEvaluationLimits as DerivationEvaluationLimits,
)
from polisyos.core.derivations import (
    DerivationInput as DerivationInput,
)
from polisyos.core.derivations import (
    DerivationMaterialization as DerivationMaterialization,
)
from polisyos.core.derivations import (
    DerivationRecipe as DerivationRecipe,
)
from polisyos.core.derivations import (
    DerivationRefusalCode as DerivationRefusalCode,
)
from polisyos.core.derivations import (
    DerivationRefusalError as DerivationRefusalError,
)
from polisyos.core.derivations import (
    DerivationRefusalReason as DerivationRefusalReason,
)
from polisyos.core.derivations import (
    DerivedParameter as DerivedParameter,
)
from polisyos.core.derivations import (
    DerivedSeries as DerivedSeries,
)
from polisyos.core.derivations import (
    ExactDecimal as ExactDecimal,
)
from polisyos.core.derivations import (
    InputContribution as InputContribution,
)
from polisyos.core.derivations import (
    ParameterOperator as ParameterOperator,
)
from polisyos.core.derivations import (
    ParameterRule as ParameterRule,
)
from polisyos.core.derivations import (
    RecipeInput as RecipeInput,
)
from polisyos.core.derivations import (
    ResolvedAssumption as ResolvedAssumption,
)
from polisyos.core.derivations import (
    SeriesPoint as SeriesPoint,
)
from polisyos.core.derivations import (
    SourceDerivationInput as SourceDerivationInput,
)
from polisyos.core.derivations import (
    SourceSeries as SourceSeries,
)
from polisyos.core.derivations import (
    TransformFamily as TransformFamily,
)
from polisyos.core.derivations import (
    TransformFamilyRegistry as TransformFamilyRegistry,
)
from polisyos.core.derivations import (
    TransformInputSpec as TransformInputSpec,
)
from polisyos.core.derivations import (
    ValueConstraint as ValueConstraint,
)
from polisyos.core.derivations import (
    _authority_input_refs as _authority_input_refs,
)
from polisyos.core.derivations import (
    _canonical_bytes as _canonical_bytes,
)
from polisyos.core.derivations import (
    _canonical_payload as _canonical_payload,
)
from polisyos.core.derivations import (
    _certificate as _certificate,
)
from polisyos.core.derivations import (
    _certificate_artifact_schema as _certificate_artifact_schema,
)
from polisyos.core.derivations import (
    _certificate_uses_selected_views as _certificate_uses_selected_views,
)
from polisyos.core.derivations import (
    _CertifiedDerivationReader as _CertifiedDerivationReader,
)
from polisyos.core.derivations import (
    _check_constraints as _check_constraints,
)
from polisyos.core.derivations import (
    _decimal_text as _decimal_text,
)
from polisyos.core.derivations import (
    _derive_parameters as _derive_parameters,
)
from polisyos.core.derivations import (
    _derive_series as _derive_series,
)
from polisyos.core.derivations import (
    _epoch_recompute_refusal as _epoch_recompute_refusal,
)
from polisyos.core.derivations import (
    _evaluate_expression as _evaluate_expression,
)
from polisyos.core.derivations import (
    _expected_certificate_inputs as _expected_certificate_inputs,
)
from polisyos.core.derivations import (
    _expected_input_edges as _expected_input_edges,
)
from polisyos.core.derivations import (
    _expected_output_inputs as _expected_output_inputs,
)
from polisyos.core.derivations import (
    _identity as _identity,
)
from polisyos.core.derivations import (
    _integer_parameter as _integer_parameter,
)
from polisyos.core.derivations import (
    _load_recipe_sources as _load_recipe_sources,
)
from polisyos.core.derivations import (
    _load_source as _load_source,
)
from polisyos.core.derivations import (
    _load_transform_family_registry_artifact as _load_transform_family_registry_artifact,
)
from polisyos.core.derivations import (
    _manifest_projection as _manifest_projection,
)
from polisyos.core.derivations import (
    _manifest_sha256 as _manifest_sha256,
)
from polisyos.core.derivations import (
    _materialize_output_basis as _materialize_output_basis,
)
from polisyos.core.derivations import (
    _output_basis_matches_family as _output_basis_matches_family,
)
from polisyos.core.derivations import (
    _producer_projection as _producer_projection,
)
from polisyos.core.derivations import (
    _projection_ref as _projection_ref,
)
from polisyos.core.derivations import (
    _put_or_verify as _put_or_verify,
)
from polisyos.core.derivations import (
    _raise_legacy_v1_unsupported as _raise_legacy_v1_unsupported,
)
from polisyos.core.derivations import (
    _read_derivation_recipe_artifact as _read_derivation_recipe_artifact,
)
from polisyos.core.derivations import (
    _recipe_artifact_schema as _recipe_artifact_schema,
)
from polisyos.core.derivations import (
    _recipe_uses_selected_views as _recipe_uses_selected_views,
)
from polisyos.core.derivations import (
    _registry_bases as _registry_bases,
)
from polisyos.core.derivations import (
    _reject_float as _reject_float,
)
from polisyos.core.derivations import (
    _require_registered_basis_units as _require_registered_basis_units,
)
from polisyos.core.derivations import (
    _resolve_assumptions as _resolve_assumptions,
)
from polisyos.core.derivations import (
    _resolve_input_ref as _resolve_input_ref,
)
from polisyos.core.derivations import (
    _resolve_recipe_family as _resolve_recipe_family,
)
from polisyos.core.derivations import (
    _revalidate_recipe as _revalidate_recipe,
)
from polisyos.core.derivations import (
    _schema_for_input_refs as _schema_for_input_refs,
)
from polisyos.core.derivations import (
    _sorted_input_refs as _sorted_input_refs,
)
from polisyos.core.derivations import (
    _StrictModel as _StrictModel,
)
from polisyos.core.derivations import (
    _UnsupportedLegacyV1Contract as _UnsupportedLegacyV1Contract,
)
from polisyos.core.derivations import (
    _validate_output_parameter_bindings as _validate_output_parameter_bindings,
)
from polisyos.core.derivations import (
    _validate_points as _validate_points,
)
from polisyos.core.derivations import (
    _verify_cached_artifact as _verify_cached_artifact,
)
from polisyos.core.derivations import (
    _verify_input_refs as _verify_input_refs,
)
from polisyos.core.derivations import (
    _verify_intake_contract as _verify_intake_contract,
)
from polisyos.core.derivations import (
    _verify_resolvable_ref as _verify_resolvable_ref,
)
from polisyos.core.derivations import (
    build_composition_recipe as build_composition_recipe,
)
from polisyos.core.derivations import (
    build_derivation_recipe as build_derivation_recipe,
)
from polisyos.core.derivations import (
    consume_certified_derivation as consume_certified_derivation,
)
from polisyos.core.derivations import (
    load_transform_family_registry as load_transform_family_registry,
)
from polisyos.core.derivations import (
    materialize_composition as materialize_composition,
)
from polisyos.core.derivations import (
    materialize_derivation as materialize_derivation,
)
from polisyos.core.derivations import (
    materialize_derivation_dag as materialize_derivation_dag,
)
from polisyos.core.derivations import (
    persist_candidate_source_series as persist_candidate_source_series,
)
from polisyos.core.derivations import (
    persist_derivation_recipe_artifact as persist_derivation_recipe_artifact,
)
from polisyos.core.derivations import (
    persist_source_series as persist_source_series,
)
from polisyos.core.derivations import (
    persist_transform_family_registry as persist_transform_family_registry,
)
from polisyos.core.derivations import (
    resolve_certified_composition as resolve_certified_composition,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.epoch_validity_cascade import EpochValidityTransitionArtifact


_EPOCH_RECOMPUTE_SCHEMA_VERSION = "polisyos.runtime.epoch-inheritance-recompute-receipt.v1"


_SELECTED_VIEW_EPOCH_RECOMPUTE_SCHEMA_VERSION = (
    "polisyos.runtime.epoch-inheritance-recompute-receipt.v1.1"
)


EPOCH_INHERITANCE_RECOMPUTE_RECEIPT_KIND = "polisyos.runtime.epoch_inheritance_recompute_receipt"


EPOCH_VALIDITY_TRANSITION_KIND = "polisyos.epoch.validity_transition"


_EPOCH_INHERITANCE_RECOMPUTE_RECEIPT_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.epoch-inheritance-recompute-receipt",
    version="1.0.0",
)


_EPOCH_INHERITANCE_RECOMPUTE_RECEIPT_SELECTED_VIEW_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.epoch-inheritance-recompute-receipt",
    version="1.1.0",
)


_EPOCH_RECOMPUTE_CONSUMER_METHOD_ID = "polisyos.runtime.quality.epoch-inheritance-recompute@1.0.0"


EpochTargetDisposition = Literal[
    "unchanged",
    "annotation_only",
    "invalidate",
    "reissue",
    "supersede",
    "withdraw",
    "contested",
    "review_required",
]


class EpochInheritanceRecomputeReceipt(_StrictModel):
    """Completed replay of one certified derivation across one transition edge.

    This receipt proves only that the owner derivation was recomputed from its
    exact certificate graph. It does not establish that the transition is the
    current history head or that its disposition authorizes a lifecycle act.
    """

    schema_version: Literal[
        _EPOCH_RECOMPUTE_SCHEMA_VERSION,
        _SELECTED_VIEW_EPOCH_RECOMPUTE_SCHEMA_VERSION,
    ] = _EPOCH_RECOMPUTE_SCHEMA_VERSION
    receipt_id: str = Field(pattern=r"^epoch-inheritance-recompute:sha256:[0-9a-f]{64}$")
    state: Literal["completed"]
    transition_artifact_ref: artifacts.ArtifactRef
    transition_artifact_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    transition_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    previous_epoch_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    current_epoch_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    requested_query_context_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_purpose: str = Field(min_length=1)
    dependency_denominator_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_ref: artifacts.ArtifactRef
    target_ref: artifacts.ArtifactRef
    relation: str = Field(min_length=1)
    target_disposition: EpochTargetDisposition
    certificate_artifact_ref: artifacts.ArtifactRef
    certificate_artifact_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    certificate_binding_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    recipe_artifact_ref: artifacts.ArtifactRef
    recipe_artifact_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    derived_artifact_ref: artifacts.ArtifactRef
    derived_output_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    certified_consumption_id: str = Field(pattern=r"^derivation-consumption:sha256:[0-9a-f]{64}$")
    predicate_class: Literal["recomputed"]
    authoritative_for: Literal["certified_derived_series_recompute"]
    may_not_use_for: tuple[
        Literal[
            "epoch_validity_transition",
            "observed_series",
            "publication",
            "source_observation",
        ],
        ...,
    ]

    @model_validator(mode="after")
    def _receipt_is_content_bound(self) -> Self:
        selected_view = any(
            ref.manifest_profile_sha256 is not None
            for ref in (
                self.transition_artifact_ref,
                self.source_ref,
                self.target_ref,
                self.certificate_artifact_ref,
                self.recipe_artifact_ref,
                self.derived_artifact_ref,
            )
        )
        expected_schema_version = (
            _SELECTED_VIEW_EPOCH_RECOMPUTE_SCHEMA_VERSION
            if selected_view
            else _EPOCH_RECOMPUTE_SCHEMA_VERSION
        )
        if self.schema_version != expected_schema_version:
            raise ValueError("epoch receipt wire version differs from selected-view presence")
        artifact_hashes = (
            (self.transition_artifact_ref, self.transition_artifact_content_hash),
            (self.certificate_artifact_ref, self.certificate_artifact_content_hash),
            (self.recipe_artifact_ref, self.recipe_artifact_content_hash),
            (self.derived_artifact_ref, self.derived_output_content_hash),
        )
        if any(str(ref.artifact_id) != content_hash for ref, content_hash in artifact_hashes):
            raise ValueError("epoch recompute artifact hash differs from exact CAS identity")
        if self.may_not_use_for != (
            "epoch_validity_transition",
            "observed_series",
            "publication",
            "source_observation",
        ):
            raise ValueError("epoch recompute authority prohibitions are not fixed")
        if self.receipt_id != _identity(
            "epoch-inheritance-recompute",
            self.identity_payload(),
        ):
            raise ValueError("epoch recompute receipt identity is not recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return every receipt field except its own identity."""

        return {
            key: value
            for key, value in self.model_dump(mode="python").items()
            if key != "receipt_id"
        }


class PersistedEpochInheritanceRecomputeReceipt(_StrictModel):
    """Ref-only handle for an exact completed recompute receipt."""

    receipt_artifact_ref: artifacts.ArtifactRef
    receipt_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _bind_receipt_ref(self) -> Self:
        if (
            self.receipt_artifact_ref.kind != EPOCH_INHERITANCE_RECOMPUTE_RECEIPT_KIND
            or self.receipt_artifact_ref.media_type != "application/json"
            or self.receipt_content_hash != str(self.receipt_artifact_ref.artifact_id)
        ):
            raise ValueError("persisted epoch recompute receipt profile differs")
        return self


def _epoch_receipt_artifact_schema(
    receipt: EpochInheritanceRecomputeReceipt,
) -> artifacts.SchemaInfo:
    return (
        _EPOCH_INHERITANCE_RECOMPUTE_RECEIPT_SELECTED_VIEW_SCHEMA
        if any(
            item.manifest_profile_sha256 is not None for item in _epoch_recompute_inputs(receipt)
        )
        else _EPOCH_INHERITANCE_RECOMPUTE_RECEIPT_SCHEMA
    )


def _read_epoch_validity_transition(
    store: artifacts.FileSystemCAS,
    transition_ref: artifacts.ArtifactRef,
) -> EpochValidityTransitionArtifact:
    from polisyos.runtime.quality import epoch_validity_cascade as epoch_cascade

    try:
        report = store.verify(transition_ref)
        raw = store.get_bytes(transition_ref)
        manifest = store.get_manifest(transition_ref)
        epoch_cascade._validate_epoch_transition_manifest(
            ref=transition_ref,
            manifest=manifest,
            raw=raw,
        )
        transition = epoch_cascade.EpochValidityTransitionArtifact.model_validate(
            _canonical_payload(raw, store=store, selector=transition_ref)
        )
    except (OSError, TypeError, ValueError, artifacts.ArtifactOwnershipError) as exc:
        raise _epoch_recompute_refusal("epoch transition artifact readback failed") from exc
    if (
        not report.ok
        or str(transition_ref.artifact_id) != f"sha256:{hashlib.sha256(raw).hexdigest()}"
        or raw != epoch_cascade._canonical_bytes(transition)
    ):
        raise _epoch_recompute_refusal("epoch transition artifact readback failed")
    return transition


def _epoch_recompute_inputs(
    receipt: EpochInheritanceRecomputeReceipt,
) -> list[artifacts.InputRef]:
    return _sorted_input_refs(
        [
            artifacts.InputRef(
                artifact_id=receipt.certificate_artifact_ref.artifact_id,
                role="derivation_certificate",
                manifest_profile_sha256=receipt.certificate_artifact_ref.manifest_profile_sha256,
            ),
            artifacts.InputRef(
                artifact_id=receipt.recipe_artifact_ref.artifact_id,
                role="derivation_recipe",
                manifest_profile_sha256=receipt.recipe_artifact_ref.manifest_profile_sha256,
            ),
            artifacts.InputRef(
                artifact_id=receipt.derived_artifact_ref.artifact_id,
                role="derived_series",
                manifest_profile_sha256=receipt.derived_artifact_ref.manifest_profile_sha256,
            ),
            artifacts.InputRef(
                artifact_id=receipt.transition_artifact_ref.artifact_id,
                role="epoch_transition",
                manifest_profile_sha256=receipt.transition_artifact_ref.manifest_profile_sha256,
            ),
            artifacts.InputRef(
                artifact_id=receipt.source_ref.artifact_id,
                role="graph_edge_source",
                manifest_profile_sha256=receipt.source_ref.manifest_profile_sha256,
            ),
            artifacts.InputRef(
                artifact_id=receipt.target_ref.artifact_id,
                role="graph_edge_target",
                manifest_profile_sha256=receipt.target_ref.manifest_profile_sha256,
            ),
        ]
    )


def _build_epoch_inheritance_recompute_receipt(
    store: artifacts.FileSystemCAS,
    *,
    transition_ref: artifacts.ArtifactRef,
    expected_previous_epoch_ref: str,
    expected_current_epoch_ref: str,
    requested_query_context_ref: str,
    authority_purpose: str,
    source_ref: artifacts.ArtifactRef,
    target_ref: artifacts.ArtifactRef,
    relation: str,
    expected_target_disposition: EpochTargetDisposition,
    certificate_ref: artifacts.ArtifactRef,
) -> EpochInheritanceRecomputeReceipt:
    transition = _read_epoch_validity_transition(store, transition_ref)
    from polisyos.runtime.quality import epoch_validity_cascade as epoch_cascade

    expected_outer_denominator_ref = epoch_cascade.epoch_dependency_outer_denominator_ref(
        certificate_bindings=transition.certificate_bindings,
        dependency_graph=transition.dependency_graph,
    )
    if (
        transition.previous_epoch_ref != expected_previous_epoch_ref
        or transition.current_epoch_ref != expected_current_epoch_ref
        or transition.requested_query_context_ref != requested_query_context_ref
        or transition.authority_purpose != authority_purpose
        or transition.dependency_denominator_ref != expected_outer_denominator_ref
    ):
        raise _epoch_recompute_refusal("epoch transition coordinates or outer denominator differ")
    matching_edges = tuple(
        edge
        for edge in transition.dependency_graph.edges
        if edge.source_ref == source_ref
        and edge.target_ref == target_ref
        and edge.relation == relation
        and edge.authority_purpose == authority_purpose
    )
    if len(matching_edges) != 1:
        raise _epoch_recompute_refusal("epoch dependency edge is absent or ambiguous")
    target_rows = tuple(
        row for row in transition.target_vector.rows if row.target_ref == target_ref
    )
    if len(target_rows) != 1 or target_rows[0].disposition != expected_target_disposition:
        raise _epoch_recompute_refusal("epoch target disposition differs from exact owner row")
    if target_ref != certificate_ref:
        raise _epoch_recompute_refusal("epoch target differs from derivation certificate")
    bindings = tuple(
        row for row in transition.certificate_bindings if row.certificate_ref == certificate_ref
    )
    if len(bindings) != 1:
        raise _epoch_recompute_refusal("epoch certificate binding is absent or ambiguous")
    binding = bindings[0]
    if (
        binding.epoch_ref != transition.previous_epoch_ref
        or binding.authority_purpose != authority_purpose
        or binding.certificate_content_hash != str(certificate_ref.artifact_id)
    ):
        raise _epoch_recompute_refusal("epoch certificate binding coordinates differ")

    recipe = _read_derivation_recipe_artifact(store, binding.recipe.recipe_ref)
    expected_roles = tuple(item.role for item in recipe.inputs)
    if (
        binding.recipe.recipe_content_hash != str(binding.recipe.recipe_ref.artifact_id)
        or binding.recipe.input_roles != expected_roles
    ):
        raise _epoch_recompute_refusal("epoch recipe binding differs from exact recipe artifact")
    consumption = consume_certified_derivation(
        store,
        certificate_ref=certificate_ref,
        consumer_method_id=_EPOCH_RECOMPUTE_CONSUMER_METHOD_ID,
    )
    try:
        certificate = DerivationCertificate.model_validate(
            _canonical_payload(
                store.get_bytes(certificate_ref), store=store, selector=certificate_ref
            )
        )
    except (OSError, TypeError, ValueError, artifacts.ArtifactOwnershipError) as exc:
        raise _epoch_recompute_refusal("derivation certificate readback failed") from exc
    if (
        certificate.recipe != recipe
        or consumption.certificate_artifact_id != certificate_ref.artifact_id
        or consumption.derived_artifact_id != certificate.derived_artifact_id
    ):
        raise _epoch_recompute_refusal("certified derivation differs from epoch binding")
    derived_ref = certificate.derived_artifact_ref or artifacts.ArtifactRef(
        artifact_id=consumption.derived_artifact_id,
        kind=DERIVED_SERIES_KIND,
        media_type="application/json",
    )
    receipt_refs = (
        transition_ref,
        source_ref,
        target_ref,
        certificate_ref,
        binding.recipe.recipe_ref,
        derived_ref,
    )
    selected_view = any(ref.manifest_profile_sha256 is not None for ref in receipt_refs)
    payload: dict[str, object] = {
        "schema_version": (
            _SELECTED_VIEW_EPOCH_RECOMPUTE_SCHEMA_VERSION
            if selected_view
            else _EPOCH_RECOMPUTE_SCHEMA_VERSION
        ),
        "state": "completed",
        "transition_artifact_ref": transition_ref,
        "transition_artifact_content_hash": str(transition_ref.artifact_id),
        "transition_content_hash": transition.transition_content_hash,
        "previous_epoch_ref": transition.previous_epoch_ref,
        "current_epoch_ref": transition.current_epoch_ref,
        "requested_query_context_ref": transition.requested_query_context_ref,
        "authority_purpose": transition.authority_purpose,
        "dependency_denominator_ref": transition.dependency_denominator_ref,
        "source_ref": source_ref,
        "target_ref": target_ref,
        "relation": relation,
        "target_disposition": target_rows[0].disposition,
        "certificate_artifact_ref": certificate_ref,
        "certificate_artifact_content_hash": str(certificate_ref.artifact_id),
        "certificate_binding_content_hash": binding.binding_content_hash,
        "recipe_artifact_ref": binding.recipe.recipe_ref,
        "recipe_artifact_content_hash": str(binding.recipe.recipe_ref.artifact_id),
        "derived_artifact_ref": derived_ref,
        "derived_output_content_hash": str(derived_ref.artifact_id),
        "certified_consumption_id": consumption.consumption_id,
        "predicate_class": "recomputed",
        "authoritative_for": "certified_derived_series_recompute",
        "may_not_use_for": (
            "epoch_validity_transition",
            "observed_series",
            "publication",
            "source_observation",
        ),
    }
    payload["receipt_id"] = _identity("epoch-inheritance-recompute", payload)
    try:
        return EpochInheritanceRecomputeReceipt.model_validate(payload)
    except ValueError as exc:
        raise _epoch_recompute_refusal("epoch recompute receipt construction failed") from exc


def produce_epoch_inheritance_recompute_receipt(
    store: artifacts.FileSystemCAS,
    *,
    transition_ref: artifacts.ArtifactRef,
    expected_previous_epoch_ref: str,
    expected_current_epoch_ref: str,
    requested_query_context_ref: str,
    authority_purpose: str,
    source_ref: artifacts.ArtifactRef,
    target_ref: artifacts.ArtifactRef,
    relation: str,
    expected_target_disposition: EpochTargetDisposition,
    certificate_ref: artifacts.ArtifactRef,
) -> PersistedEpochInheritanceRecomputeReceipt:
    """Replay one certified derivation and persist a completed-only receipt."""

    receipt = _build_epoch_inheritance_recompute_receipt(
        store,
        transition_ref=transition_ref,
        expected_previous_epoch_ref=expected_previous_epoch_ref,
        expected_current_epoch_ref=expected_current_epoch_ref,
        requested_query_context_ref=requested_query_context_ref,
        authority_purpose=authority_purpose,
        source_ref=source_ref,
        target_ref=target_ref,
        relation=relation,
        expected_target_disposition=expected_target_disposition,
        certificate_ref=certificate_ref,
    )
    ref, _ = _put_or_verify(
        store,
        payload=receipt,
        kind=EPOCH_INHERITANCE_RECOMPUTE_RECEIPT_KIND,
        schema=_epoch_receipt_artifact_schema(receipt),
        inputs=_epoch_recompute_inputs(receipt),
        refusal_code=DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
    )
    return PersistedEpochInheritanceRecomputeReceipt(
        receipt_artifact_ref=ref,
        receipt_content_hash=str(ref.artifact_id),
    )


def read_epoch_inheritance_recompute_receipt(
    store: artifacts.FileSystemCAS,
    *,
    receipt_ref: artifacts.ArtifactRef,
    expected_previous_epoch_ref: str,
    expected_current_epoch_ref: str,
    requested_query_context_ref: str,
    authority_purpose: str,
    source_ref: artifacts.ArtifactRef,
    target_ref: artifacts.ArtifactRef,
    relation: str,
    expected_target_disposition: EpochTargetDisposition,
    certificate_ref: artifacts.ArtifactRef,
) -> PersistedEpochInheritanceRecomputeReceipt:
    """Exact-read a receipt and replay every referenced owner artifact."""

    if (
        receipt_ref.kind != EPOCH_INHERITANCE_RECOMPUTE_RECEIPT_KIND
        or receipt_ref.media_type != "application/json"
    ):
        raise _epoch_recompute_refusal("epoch recompute receipt profile mismatch")
    try:
        receipt = EpochInheritanceRecomputeReceipt.model_validate(
            _canonical_payload(store.get_bytes(receipt_ref), store=store, selector=receipt_ref)
        )
    except (OSError, TypeError, ValueError, artifacts.ArtifactOwnershipError) as exc:
        raise _epoch_recompute_refusal("epoch recompute receipt readback failed") from exc
    _verify_cached_artifact(
        store,
        artifact_ref=receipt_ref,
        expected_bytes=_canonical_bytes(receipt),
        kind=EPOCH_INHERITANCE_RECOMPUTE_RECEIPT_KIND,
        schema=_epoch_receipt_artifact_schema(receipt),
        producer=_DERIVATION_PRODUCER,
        inputs=_epoch_recompute_inputs(receipt),
        refusal_code=DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
    )
    rebuilt = _build_epoch_inheritance_recompute_receipt(
        store,
        transition_ref=receipt.transition_artifact_ref,
        expected_previous_epoch_ref=expected_previous_epoch_ref,
        expected_current_epoch_ref=expected_current_epoch_ref,
        requested_query_context_ref=requested_query_context_ref,
        authority_purpose=authority_purpose,
        source_ref=source_ref,
        target_ref=target_ref,
        relation=relation,
        expected_target_disposition=expected_target_disposition,
        certificate_ref=certificate_ref,
    )
    if rebuilt != receipt:
        raise _epoch_recompute_refusal("epoch recompute receipt differs after owner replay")
    return PersistedEpochInheritanceRecomputeReceipt(
        receipt_artifact_ref=receipt_ref,
        receipt_content_hash=str(receipt_ref.artifact_id),
    )


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
    "CANDIDATE_SOURCE_SERIES_KIND",
    "COMPOSITION_DERIVATION_SCHEMA_VERSION",
    "DERIVATION_CERTIFICATE_KIND",
    "DERIVATION_RECIPE_KIND",
    "DERIVATION_SCHEMA_VERSION",
    "DERIVED_SERIES_KIND",
    "ECONOMIC_SERIES_KIND",
    "EPOCH_INHERITANCE_RECOMPUTE_RECEIPT_KIND",
    "EPOCH_VALIDITY_TRANSITION_KIND",
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
    "DerivedEconomicSeries",
    "DerivedParameter",
    "DerivedSeries",
    "EconomicBasis",
    "EconomicSeries",
    "EpochInheritanceRecomputeReceipt",
    "EpochTargetDisposition",
    "InputContribution",
    "ParameterRule",
    "PersistedEpochInheritanceRecomputeReceipt",
    "PriceIndexBasis",
    "PriceIndexSeries",
    "RecipeInput",
    "ResolvedAssumption",
    "SeriesPoint",
    "SourceDerivationInput",
    "SourceSeries",
    "TransformFamily",
    "TransformFamilyRegistry",
    "TransformInputSpec",
    "build_composition_recipe",
    "build_cpi_derivation_recipe",
    "build_derivation_recipe",
    "consume_certified_derivation",
    "load_transform_family_registry",
    "materialize_composition",
    "materialize_cpi_real_terms",
    "materialize_derivation",
    "materialize_derivation_dag",
    "persist_candidate_source_series",
    "persist_derivation_recipe_artifact",
    "persist_economic_series",
    "persist_price_index_series",
    "persist_source_series",
    "persist_transform_family_registry",
    "produce_epoch_inheritance_recompute_receipt",
    "read_epoch_inheritance_recompute_receipt",
    "resolve_certified_composition",
]
