"""Derivation, universality, and capstone-route evidence projections."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from polisyos.core import artifacts
from polisyos.fabric.data_plane import content_sha256
from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
    CensusManifest,
    semantic_content_hash,
)
from tools.quality.validation.layer3_gy_n13b_acceptance import (
    AcceptanceCaseReceipt,
    verify_persisted_acceptance_case,
)
from tools.quality.validation.layer3_gy_n13b_derivation_universality import (
    DerivationUniversalityReceipt,
)

from .acquisition_contract_support import (
    SHA256_PATTERN,
    _json_value,
    _StrictModel,
)


class DerivationProjection(_StrictModel):
    """Narrow D4–D6 acceptance projection over one verified CAS recipe."""

    recipe_id: str = Field(pattern=r"^derivation-recipe:sha256:[0-9a-f]{64}$")
    recipe_projection: dict[str, Any]
    recipe_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    nominal_artifact_id: str = Field(pattern=SHA256_PATTERN)
    deflator_artifact_id: str = Field(pattern=SHA256_PATTERN)
    derived_artifact_id: str = Field(pattern=SHA256_PATTERN)
    certificate_artifact_id: str = Field(pattern=SHA256_PATTERN)
    first_materialization_cache_hit: Literal[False]
    second_materialization_cache_hit: Literal[True]
    consumer_method_ids: tuple[str, str]
    consumer_count: Literal[2]
    distinct_consumer_count: Literal[2]
    observation_class: Literal["derived"]
    effective_authority: str = Field(min_length=1)
    basis_mismatch_refusal_code: Literal["basis_mismatch"]
    model_output_observation_rejection_codes: tuple[
        Literal["model_output_not_observation"],
        ...,
    ]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _acceptance_is_content_bound(self) -> Self:
        if self.recipe_projection.get("recipe_id") != self.recipe_id:
            raise ValueError("derivation projection recipe identity drift")
        if self.recipe_projection_sha256 != content_sha256(self.recipe_projection):
            raise ValueError("derivation recipe projection hash drift")
        if self.consumer_method_ids != tuple(sorted(set(self.consumer_method_ids))):
            raise ValueError("derivation consumers must be distinct and sorted")
        if self.consumer_count != len(self.consumer_method_ids) or (
            self.distinct_consumer_count != len(set(self.consumer_method_ids))
        ):
            raise ValueError("derivation consumer denominator drift")
        if self.model_output_observation_rejection_codes != ("model_output_not_observation",):
            raise ValueError("class-(iv) output must fail observation admission closed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("derivation projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


def derive_derivation_projection(
    *,
    acceptance: AcceptanceCaseReceipt,
    cas_root: Path,
) -> DerivationProjection:
    """Reopen the CAS graph and bind the exact recipe/consumer acceptance case."""

    frozen = AcceptanceCaseReceipt.model_validate(acceptance.model_dump(mode="python"))
    store = artifacts.FileSystemCAS(Path(cas_root))
    verify_persisted_acceptance_case(store, frozen)
    recipe = frozen.recipe.model_dump(mode="json")
    consumers = tuple(sorted(row.consumer_method_id for row in frozen.consumers))
    values = {
        "recipe_id": frozen.recipe.recipe_id,
        "recipe_projection": recipe,
        "recipe_projection_sha256": content_sha256(recipe),
        "nominal_artifact_id": frozen.nominal_series_artifact_id,
        "deflator_artifact_id": frozen.deflator_series_artifact_id,
        "derived_artifact_id": frozen.derived_artifact_id,
        "certificate_artifact_id": frozen.certificate_artifact_id,
        "first_materialization_cache_hit": frozen.first_materialization_cache_hit,
        "second_materialization_cache_hit": frozen.second_materialization_cache_hit,
        "consumer_method_ids": consumers,
        "consumer_count": len(frozen.consumers),
        "distinct_consumer_count": len(set(consumers)),
        "observation_class": frozen.certificate.observation_class,
        "effective_authority": str(frozen.certificate.effective_authority),
        "basis_mismatch_refusal_code": frozen.basis_mismatch_refusal_code,
        "model_output_observation_rejection_codes": (
            frozen.model_output_observation_rejection_codes
        ),
    }
    return DerivationProjection(
        **values,
        projection_sha256=content_sha256(_json_value(values)),
    )


class UniversalityFamilyProjection(_StrictModel):
    """Narrow proof that one data-registered family used the generic owner."""

    family_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    family_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    recipe_id: str = Field(pattern=r"^derivation-recipe:sha256:[0-9a-f]{64}$")
    recipe_sha256: str = Field(pattern=SHA256_PATTERN)
    certificate_artifact_id: str = Field(pattern=SHA256_PATTERN)
    derived_artifact_id: str = Field(pattern=SHA256_PATTERN)
    selected_role_projection_sha256s: tuple[str, ...] = Field(min_length=1)
    parameter_rule_operators: tuple[str, ...]
    assumption_names: tuple[str, ...] = Field(min_length=1)
    first_materialization_cache_hit: Literal[False]
    second_materialization_cache_hit: Literal[True]
    fresh_cas_rebuild_equal: Literal[True]
    monotone_authority_proven: Literal[True]
    observation_class: Literal["derived"]
    family_proof_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _family_projection_is_canonical(self) -> Self:
        if self.selected_role_projection_sha256s != tuple(
            sorted(set(self.selected_role_projection_sha256s))
        ):
            raise ValueError("universality role projections must be unique and sorted")
        if self.assumption_names != tuple(sorted(set(self.assumption_names))):
            raise ValueError("universality assumption names must be unique and sorted")
        return self


class DerivationUniversalityProjection(_StrictModel):
    """Projection-scoped A1–A5 proof over the full transform-family registry."""

    registry_ref: str = Field(min_length=1)
    registry_sha256: str = Field(pattern=SHA256_PATTERN)
    source_epoch: Literal[0]
    full_series_denominator_count: int = Field(ge=1)
    family_count: int = Field(ge=1)
    families: tuple[UniversalityFamilyProjection, ...] = Field(min_length=1)
    unregistered_basis_refusal_code: Literal["basis_mismatch"]
    unregistered_basis_refusal_reason: Literal["no_certified_transform"]
    network_call_count: Literal[0]
    source_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _registry_denominator_is_recomputed(self) -> Self:
        family_identities = tuple((row.family_id, row.method_version) for row in self.families)
        if family_identities != tuple(sorted(set(family_identities))):
            raise ValueError("universality family denominator must be unique and sorted")
        if self.family_count != len(self.families):
            raise ValueError("universality family count must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("derivation universality projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


def derive_derivation_universality_projection(
    receipt: DerivationUniversalityReceipt,
) -> DerivationUniversalityProjection:
    """Bind only decisive genericity fields from the recomputing receipt."""

    frozen = DerivationUniversalityReceipt.model_validate(receipt.model_dump(mode="python"))
    rows = tuple(
        UniversalityFamilyProjection(
            family_id=proof.family_id,
            method_version=proof.method_version,
            family_projection_sha256=proof.family_projection_sha256,
            recipe_id=proof.recipe.recipe_id,
            recipe_sha256=proof.recipe_sha256,
            certificate_artifact_id=proof.certificate_artifact_id,
            derived_artifact_id=proof.derived_artifact_id,
            selected_role_projection_sha256s=tuple(
                sorted(selection.selected.projection_sha256 for selection in proof.selections)
            ),
            parameter_rule_operators=tuple(
                parameter.rule.operator for parameter in proof.recipe.parameters
            ),
            assumption_names=tuple(
                sorted(assumption.name for assumption in proof.recipe.assumptions)
            ),
            first_materialization_cache_hit=proof.first_materialization_cache_hit,
            second_materialization_cache_hit=proof.second_materialization_cache_hit,
            fresh_cas_rebuild_equal=proof.fresh_cas_rebuild_equal,
            monotone_authority_proven=proof.monotone_authority_proven,
            observation_class=proof.certificate.observation_class,
            family_proof_sha256=proof.proof_sha256,
        )
        for proof in frozen.family_proofs
    )
    values = {
        "registry_ref": frozen.registry_ref,
        "registry_sha256": frozen.registry_sha256,
        "source_epoch": frozen.source_epoch,
        "full_series_denominator_count": frozen.full_series_denominator_count,
        "family_count": frozen.family_count,
        "families": rows,
        "unregistered_basis_refusal_code": frozen.unregistered_basis_refusal_code,
        "unregistered_basis_refusal_reason": frozen.unregistered_basis_refusal_reason,
        "network_call_count": frozen.network_call_count,
        "source_receipt_sha256": frozen.receipt_sha256,
    }
    return DerivationUniversalityProjection(
        **values,
        projection_sha256=content_sha256(_json_value(values)),
    )


class CapstoneRouteRow(_StrictModel):
    """Decisive N13a route fields sufficient to recompute its class."""

    route_id: str = Field(min_length=1)
    witness_kind: str = Field(min_length=1)
    row_addressable_variable: str | None
    row_addressable_local_observation_count: int | None = Field(default=None, ge=0)
    row_addressable_executable_binding_count: int | None = Field(default=None, ge=0)
    missing_link: str = Field(min_length=1)
    route_class: Literal[
        "local_lift",
        "live_fetchable",
        "not_a_data_gap",
        "unresolved",
    ]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _route_class_is_recomputed(self) -> Self:
        if self.witness_kind != "owner_data_gap":
            expected = "not_a_data_gap"
        elif self.row_addressable_variable is None:
            raise ValueError("owner data gap requires a row-addressable variable")
        elif (self.row_addressable_local_observation_count or 0) > 0:
            expected = "local_lift"
        elif (self.row_addressable_executable_binding_count or 0) > 0:
            expected = "live_fetchable"
        else:
            expected = "unresolved"
        if self.route_class != expected:
            raise ValueError("capstone route class must be recomputed from decisive evidence")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("capstone route projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class CapstoneRoutePreservation(_StrictModel):
    """Three-route N13a fence proving no data-support laundering."""

    source_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    routes: tuple[CapstoneRouteRow, ...] = Field(min_length=3, max_length=3)
    route_count: Literal[3]
    laundered_route_count: int = Field(ge=0)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _denominator_and_fence_are_recomputed(self) -> Self:
        route_ids = tuple(row.route_id for row in self.routes)
        if route_ids != tuple(sorted(set(route_ids))):
            raise ValueError("capstone route denominator must be unique and sorted")
        if self.route_count != len(self.routes):
            raise ValueError("capstone route count drift")
        laundered = sum(row.route_class != "not_a_data_gap" for row in self.routes)
        if self.laundered_route_count != laundered:
            raise ValueError("capstone route laundering count must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("capstone preservation identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


def derive_capstone_route_preservation(census: CensusManifest) -> CapstoneRoutePreservation:
    """Project only decisive route-class inputs from the validated N13a census."""

    frozen = CensusManifest.model_validate(census.model_dump(mode="python"))
    rows: list[CapstoneRouteRow] = []
    for evidence in frozen.route_evidence:
        supply = evidence.row_addressable_supply
        values = {
            "route_id": evidence.route.route_id,
            "witness_kind": evidence.route.witness_kind,
            "row_addressable_variable": evidence.route.row_addressable_variable,
            "row_addressable_local_observation_count": (
                supply.local_observation_count if supply is not None else None
            ),
            "row_addressable_executable_binding_count": (
                supply.executable_binding_count if supply is not None else None
            ),
            "missing_link": evidence.route.missing_link,
            "route_class": evidence.route_class.value,
        }
        rows.append(
            CapstoneRouteRow(
                **values,
                projection_sha256=content_sha256(values),
            )
        )
    rows = sorted(rows, key=lambda row: row.route_id)
    values = {
        "source_projection_sha256": semantic_content_hash(frozen.route_evidence),
        "routes": tuple(rows),
        "route_count": len(rows),
        "laundered_route_count": sum(row.route_class != "not_a_data_gap" for row in rows),
    }
    return CapstoneRoutePreservation(
        **values,
        projection_sha256=content_sha256(_json_value(values)),
    )
