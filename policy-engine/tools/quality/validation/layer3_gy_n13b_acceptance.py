"""Recomputing owners for the GY-N13b real-terms acceptance inputs.

The selector is deliberately read-only. It enumerates every local Ukraine
series group before applying family-owned input bases and catalog-role policy.
It never treats a catalog label as admission evidence and never performs I/O.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from string import Formatter
from typing import Any, Literal, Self

import duckdb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.data_forge.read_api.catalog import (
    CatalogSelectionCandidateEvidence,
    CatalogSelectionPolicyConfig,
    CatalogSelectionRoleConfig,
)
from polisyos.fabric.data_plane import (
    LiveAttemptTerminal,
    canonical_json_bytes,
    content_sha256,
    resolve_live_attempt_terminals,
)
from polisyos.foundry.methods.catalog.forecasting.univariate import (
    ExponentialSmoothingEstimator,
    ThetaMethodEstimator,
)
from polisyos.runtime.quality.acquisition_executor import (
    ObservationProvenanceClass,
    derive_observation_provenance_rejections,
)
from polisyos.runtime.quality.derived_observations import (
    DERIVATION_CERTIFICATE_KIND,
    AuthorityProjection,
    BasisSignature,
    CertifiedDerivationConsumption,
    DerivationCertificate,
    DerivationRecipe,
    DerivationRefusalCode,
    DerivationRefusalError,
    DerivationRefusalReason,
    SeriesPoint,
    SourceSeries,
    TransformFamily,
    TransformFamilyRegistry,
    TransformInputSpec,
    build_derivation_recipe,
    consume_certified_derivation,
    load_transform_family_registry,
    materialize_derivation,
    persist_source_series,
)
from tools.quality.validation.layer3_gy_acquisition_executor import (
    DEFAULT_TARGET_AUTHORITY_PROVISION,
    DEFAULT_TARGET_AUTHORITY_REGISTRY,
    LiveTargetSelection,
    bytes_sha256,
    derive_live_attempt_id,
    derive_target_authority_owners,
    derive_target_family_receipt,
)

DEFAULT_ACCEPTANCE_INPUT_SELECTION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acceptance_input_selection.json"
)
DEFAULT_ACCEPTANCE_DEFLATOR_HARNESS = Path(
    "architecture/policy_design_case/layer3_gy_n13b_worldbank_cpi_harness.json"
)
DEFAULT_ACCEPTANCE_AUTHORITY_OWNER = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acceptance_authority_owner.json"
)
DEFAULT_ACCEPTANCE_LIVE_EXECUTION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_cpi_live_execution_evidence.json"
)
DEFAULT_ACCEPTANCE_FALLBACK_SELECTION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acceptance_fallback_selection.json"
)
DEFAULT_ACCEPTANCE_CASE = Path(
    "architecture/policy_design_case/layer3_gy_n13b_derived_acceptance_case.json"
)
DEFAULT_DERIVATION_FAMILY_REGISTRY = Path(
    "architecture/production_quality/derivation_family_registry.toml"
)

_ACCEPTANCE_PRODUCER = artifacts.ProducerInfo(
    component="tools.quality.validation.layer3_gy_n13b_acceptance",
    version="2.0.0",
)
_ACCEPTANCE_EVIDENCE_SCHEMA = artifacts.SchemaInfo(
    name="policyos.layer3.gy.n13b.series-input-evidence",
    version="1.0.0",
)


class AcceptanceSelectionError(RuntimeError):
    """Typed refusal raised when the acceptance denominator cannot be resolved."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail or code}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class AcceptanceDerivationOwner:
    """Narrow selected family plus its catalog-role selector."""

    registry: TransformFamilyRegistry
    family: TransformFamily
    selector: CatalogSelectionPolicyConfig

    @property
    def primary_role(self) -> str:
        """Return the family-owned year-domain role."""

        return self.family.year_domain_role

    @property
    def auxiliary_role(self) -> str:
        """Return the sole non-primary role required by this two-input case."""

        roles = tuple(
            spec.role for spec in self.family.input_specs if spec.role != self.primary_role
        )
        if len(roles) != 1:
            raise AcceptanceSelectionError(
                "acceptance_auxiliary_role_unresolved", self.family.family_id
            )
        return roles[0]

    def selection_role(self, role: str) -> CatalogSelectionRoleConfig:
        """Return the exact selector role bound to one family input."""

        return next(item for item in self.selector.roles if item.role == role)

    @property
    def family_projection_sha256(self) -> str:
        """Return selected-family identity without unrelated registry growth."""

        return content_sha256(self.family.model_dump(mode="json"))

    @property
    def selector_projection_sha256(self) -> str:
        """Return the selected catalog-role policy identity."""

        return content_sha256(self.selector.identity_payload())


class LocalNominalPoint(_StrictModel):
    """One content-bound exact-year point selected from immutable epoch zero."""

    observation_id: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2200)
    value: Decimal
    source_watermark: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    acquisition_method: str = Field(min_length=1)


class LocalNominalDisposition(_StrictModel):
    """One local series group and its evidence-derived acceptance disposition."""

    dataset_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    agency: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str
    access_license: str
    raw_variable: str = Field(min_length=1)
    metric_id: str | None
    canonical_variable: str = Field(min_length=1)
    role_policy: CatalogSelectionRoleConfig
    derived_unit: str | None
    row_count: int = Field(ge=1)
    distinct_year_count: int = Field(ge=1)
    minimum_year: int = Field(ge=1900, le=2200)
    maximum_year: int = Field(ge=1900, le=2200)
    duplicate_year_count: int = Field(ge=0)
    source_watermark_count: int = Field(ge=0)
    dataset_version_count: int = Field(ge=0)
    acquisition_method_count: int = Field(ge=0)
    alignment_method: str | None
    alignment_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    alignment_is_proxy: bool | None
    alignment_proxy_penalty: float | None = Field(default=None, ge=0.0, le=1.0)
    exact_binding_count: int = Field(ge=0)
    maximum_binding_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    maximum_distribution_quality: float | None = Field(default=None, ge=0.0, le=1.0)
    acceptance_alignment_score: float = Field(ge=0.0, le=1.0)
    rejection_codes: tuple[str, ...]
    eligible: bool
    observation_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _disposition_is_recomputed(self) -> Self:
        expected_unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(
            f"{self.title} {self.description}"
        )
        if self.derived_unit != expected_unit:
            raise ValueError("local nominal unit must come from the catalog owner")
        expected_rejections = _local_rejection_codes(self)
        if self.rejection_codes != expected_rejections:
            raise ValueError("local nominal rejection codes must be recomputed")
        if self.eligible != (not expected_rejections):
            raise ValueError("local nominal eligibility must derive from rejection codes")
        evaluation = _evaluate_local_candidate(self)
        if abs(self.acceptance_alignment_score - evaluation.semantic_alignment_score) > 1e-9:
            raise ValueError("local nominal acceptance score must use the alignment owner")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("local nominal projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the narrow series disposition without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class DeflatorCarrierDisposition(_StrictModel):
    """One live binding classified for the family-declared auxiliary role."""

    metric_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    distribution_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    role_policy: CatalogSelectionRoleConfig
    binding_confidence: float = Field(ge=0.0, le=1.0)
    execution_tier: str = Field(min_length=1)
    source: str = Field(min_length=1)
    agency: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str
    access_license: str
    access_auth_required: bool
    parser_supported: bool
    distribution_quality_score: float = Field(ge=0.0, le=1.0)
    source_locator: str = Field(min_length=1)
    temporal_start: str | None
    temporal_end: str | None
    themes: tuple[str, ...]
    derived_unit: str | None
    reference_base_year: int | None = Field(default=None, ge=1900, le=2200)
    live_family: bool
    acceptance_alignment_score: float = Field(ge=0.0, le=1.0)
    rejection_codes: tuple[str, ...]
    eligible: bool
    projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _disposition_is_recomputed(self) -> Self:
        if self.themes != tuple(sorted(set(self.themes))):
            raise ValueError("deflator themes must be unique and sorted")
        expected_unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(
            f"{self.title} {self.description}"
        )
        if self.derived_unit != expected_unit:
            raise ValueError("deflator unit must come from the catalog owner")
        expected_year = _reference_base_year(
            f"{self.title} {self.description}",
            pattern=self.role_policy.reference_value_pattern,
        )
        if self.reference_base_year != expected_year:
            raise ValueError("deflator base year must be parsed from catalog evidence")
        expected_rejections = _deflator_rejection_codes(self)
        if self.rejection_codes != expected_rejections:
            raise ValueError("deflator rejection codes must be recomputed")
        if self.eligible != (not expected_rejections):
            raise ValueError("deflator eligibility must derive from rejection codes")
        evaluation = _evaluate_live_candidate(self)
        if abs(self.acceptance_alignment_score - evaluation.semantic_alignment_score) > 1e-9:
            raise ValueError("deflator rank must use the alignment owner")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("deflator projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the carrier disposition without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class AcceptanceInputSelection(_StrictModel):
    """Full-denominator owner for one real-terms acceptance input pair."""

    schema_version: Literal["policyos.layer3.gy.n13b.acceptance_inputs.v1"] = (
        "policyos.layer3.gy.n13b.acceptance_inputs.v1"
    )
    baseline_ref: str = Field(min_length=1)
    baseline_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    census_family_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    transform_family_id: str = Field(min_length=1)
    transform_family_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    selector_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    primary_input_role: str = Field(min_length=1)
    auxiliary_input_role: str = Field(min_length=1)
    country_code: str = Field(min_length=2, max_length=3)
    all_local_series_group_count: int = Field(ge=1)
    non_monetary_series_group_count: int = Field(ge=0)
    local_monetary_denominator_count: int = Field(ge=1)
    eligible_local_nominal_count: int = Field(ge=0)
    local_rejection_counts: dict[str, int]
    local_monetary_denominator: tuple[LocalNominalDisposition, ...] = Field(min_length=1)
    inflation_binding_denominator_count: int = Field(ge=1)
    eligible_deflator_count: int = Field(ge=0)
    deflator_rejection_counts: dict[str, int]
    deflator_denominator: tuple[DeflatorCarrierDisposition, ...] = Field(min_length=1)
    disposition: Literal["admissible_pair", "acceptance_inputs_inadmissible"]
    selected_nominal: LocalNominalDisposition | None
    selected_nominal_points: tuple[LocalNominalPoint, ...]
    selected_deflator: DeflatorCarrierDisposition | None
    execution_selection: LiveTargetSelection | None
    request_start_year: int | None = Field(default=None, ge=1960, le=2200)
    request_end_year: int | None = Field(default=None, ge=1960, le=2200)
    request_page_size: int | None = Field(default=None, ge=1, le=20_000)
    paid_success_elapsed_seconds: float = Field(gt=0.0)
    timeout_multiplier: Literal[2]
    derived_timeout_cap_seconds: float = Field(gt=0.0)
    selection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _selection_is_recomputed(self) -> Self:
        if self.primary_input_role == self.auxiliary_input_role:
            raise ValueError("acceptance input roles must be distinct")
        if self.all_local_series_group_count != (
            self.non_monetary_series_group_count + self.local_monetary_denominator_count
        ):
            raise ValueError("local acceptance denominator must cover every series group")
        if self.local_monetary_denominator_count != len(self.local_monetary_denominator):
            raise ValueError("local monetary denominator count drift")
        if self.inflation_binding_denominator_count != len(self.deflator_denominator):
            raise ValueError("deflator denominator count drift")
        local_eligible = tuple(row for row in self.local_monetary_denominator if row.eligible)
        deflator_eligible = tuple(row for row in self.deflator_denominator if row.eligible)
        if self.eligible_local_nominal_count != len(local_eligible):
            raise ValueError("local eligible denominator count drift")
        if self.eligible_deflator_count != len(deflator_eligible):
            raise ValueError("deflator eligible denominator count drift")
        if self.local_rejection_counts != _rejection_counts(self.local_monetary_denominator):
            raise ValueError("local rejection census must be recomputed")
        if self.deflator_rejection_counts != _rejection_counts(self.deflator_denominator):
            raise ValueError("deflator rejection census must be recomputed")
        pair_exists = bool(local_eligible and deflator_eligible)
        expected_disposition = (
            "admissible_pair" if pair_exists else "acceptance_inputs_inadmissible"
        )
        if self.disposition != expected_disposition:
            raise ValueError("acceptance disposition must derive from both denominators")
        optional_values = (
            self.selected_nominal,
            self.selected_deflator,
            self.execution_selection,
            self.request_start_year,
            self.request_end_year,
            self.request_page_size,
        )
        if pair_exists and any(value is None for value in optional_values):
            raise ValueError("admissible acceptance pair requires a complete execution scope")
        if not pair_exists and any(value is not None for value in optional_values):
            raise ValueError("inadmissible acceptance inputs cannot select an execution scope")
        if pair_exists:
            assert self.selected_nominal is not None
            assert self.selected_deflator is not None
            assert self.execution_selection is not None
            if (
                self.selected_nominal not in local_eligible
                or self.selected_deflator not in deflator_eligible
            ):
                raise ValueError("selected acceptance inputs must belong to eligible denominators")
            if len(self.selected_nominal_points) != self.selected_nominal.distinct_year_count:
                raise ValueError("selected nominal point denominator drift")
            point_projection = _point_projection_sha256(self.selected_nominal_points)
            if point_projection != self.selected_nominal.observation_projection_sha256:
                raise ValueError("selected nominal points must bind the local observation owner")
            years = tuple(point.year for point in self.selected_nominal_points)
            if years != tuple(sorted(set(years))):
                raise ValueError("selected nominal years must be unique and sorted")
            if (
                self.request_start_year
                != min(years[0], self.selected_deflator.reference_base_year or years[0])
                or self.request_end_year != years[-1]
            ):
                raise ValueError("deflator request scope must cover base and every nominal year")
            if self.request_page_size != self.request_end_year - self.request_start_year + 1:
                raise ValueError("deflator page size must derive from the exact year window")
            if (
                self.execution_selection.request_dataset_id
                != self.selected_deflator.request_dataset_id
                or self.execution_selection.source_catalog_dataset_id
                != self.selected_deflator.dataset_id
                or self.execution_selection.source_catalog_distribution_id
                != self.selected_deflator.distribution_id
            ):
                raise ValueError("execution selection must preserve the selected deflator carrier")
        elif self.selected_nominal_points:
            raise ValueError("inadmissible acceptance inputs cannot carry nominal points")
        expected_timeout = float(
            __import__("math").ceil(self.paid_success_elapsed_seconds * self.timeout_multiplier)
        )
        if self.derived_timeout_cap_seconds != expected_timeout:
            raise ValueError("acceptance timeout must derive from paid success latency")
        if self.selection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("acceptance selection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the full denominator projection without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "selection_sha256"
        }


class AcceptanceAuthorityOwner(_StrictModel):
    """Projection binding the selected carrier to the canonical authority graph."""

    schema_version: Literal["policyos.layer3.gy.n13b.acceptance_authority.v1"] = (
        "policyos.layer3.gy.n13b.acceptance_authority.v1"
    )
    input_selection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    input_selection_file_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    baseline_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    l5_measurement_registry_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_entry_id: str = Field(pattern=r"^acquisition-authority:sha256:[0-9a-f]{64}$")
    live_attempt_id: str = Field(min_length=1)
    live_harness_content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    combined_registry_content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    combined_provision_id: str = Field(
        pattern=r"^acquisition-authority-provision:sha256:[0-9a-f]{64}$"
    )
    registry_entry_count: int = Field(ge=2)
    live_harness_receipt_count: int = Field(ge=2)
    owner_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _owner_is_content_bound(self) -> Self:
        if self.owner_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("acceptance authority owner identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the authority projection without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "owner_sha256"
        }


class AcceptanceLiveExecutionReceipt(_StrictModel):
    """Reopened journal/CAS result for the single authorized auxiliary call."""

    schema_version: Literal["policyos.layer3.gy.n13b.acceptance_live_execution.v1"] = (
        "policyos.layer3.gy.n13b.acceptance_live_execution.v1"
    )
    input_selection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_owner_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    attempt_id: str = Field(min_length=1)
    disposition: Literal["measured_pending_passport", "live_execution_terminal"]
    call_count: int = Field(ge=0)
    terminal: LiveAttemptTerminal
    live_source_execution: Any | None
    baseline_before_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    baseline_after_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _receipt_is_recomputed(self) -> Self:
        if self.terminal.attempt_id != self.attempt_id:
            raise ValueError("acceptance terminal must preserve the authorized attempt")
        if self.baseline_before_sha256 != self.baseline_after_sha256:
            raise ValueError("acceptance live call must preserve immutable epoch zero")
        if self.live_source_execution is None:
            if self.disposition != "live_execution_terminal":
                raise ValueError("missing live evidence must remain a typed terminal")
        else:
            evidence = data_forge_read_api.catalog.LiveSourceExecutionEvidence.model_validate(
                self.live_source_execution
            )
            if (
                self.disposition != "measured_pending_passport"
                or self.terminal.failure_code != "measured_pending_passport"
                or evidence.authorization.attempt_id != self.attempt_id
                or evidence.call_count != self.call_count
                or evidence.raw_evidence_ref != self.terminal.raw_evidence_ref
                or evidence.baseline_before_sha256 != self.baseline_before_sha256
                or evidence.baseline_after_sha256 != self.baseline_after_sha256
            ):
                raise ValueError("acceptance live evidence graph is not content-bound")
        if self.receipt_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("acceptance live execution identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the execution receipt without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "receipt_sha256"
        }


class LocalDeflatorPoint(_StrictModel):
    """One exact-year local price-index observation from immutable epoch zero."""

    observation_id: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2200)
    value: Decimal = Field(gt=0)
    source_watermark: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    acquisition_method: str = Field(min_length=1)


class LocalDeflatorDisposition(_StrictModel):
    """One local index series classified for the real-terms deflator role."""

    dataset_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    agency: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str
    access_license: str
    raw_variable: str = Field(min_length=1)
    metric_id: str | None
    canonical_variable: str = Field(min_length=1)
    role_policy: CatalogSelectionRoleConfig
    row_count: int = Field(ge=1)
    distinct_year_count: int = Field(ge=1)
    minimum_year: int = Field(ge=1900, le=2200)
    maximum_year: int = Field(ge=1900, le=2200)
    duplicate_year_count: int = Field(ge=0)
    source_watermark_count: int = Field(ge=0)
    dataset_version_count: int = Field(ge=0)
    acquisition_method_count: int = Field(ge=0)
    nonpositive_value_count: int = Field(ge=0)
    alignment_method: str | None
    alignment_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    alignment_is_proxy: bool | None
    alignment_proxy_penalty: float | None = Field(default=None, ge=0.0, le=1.0)
    exact_binding_count: int = Field(ge=0)
    maximum_binding_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    maximum_distribution_quality: float | None = Field(default=None, ge=0.0, le=1.0)
    derived_unit: str | None
    reference_base_year: int | None = Field(default=None, ge=1900, le=2200)
    overlapping_nominal_years: tuple[int, ...]
    missing_nominal_years: tuple[int, ...]
    rejection_codes: tuple[str, ...]
    eligible: bool
    observation_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _disposition_is_recomputed(self) -> Self:
        if self.overlapping_nominal_years != tuple(sorted(set(self.overlapping_nominal_years))):
            raise ValueError("local deflator overlap years must be unique and sorted")
        if self.missing_nominal_years != tuple(sorted(set(self.missing_nominal_years))):
            raise ValueError("local deflator missing years must be unique and sorted")
        expected_unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(
            f"{self.title} {self.description}"
        )
        if self.derived_unit != expected_unit:
            raise ValueError("local deflator unit must come from the catalog owner")
        expected_year = _reference_base_year(
            f"{self.title} {self.description}",
            pattern=self.role_policy.reference_value_pattern,
        )
        if self.reference_base_year != expected_year:
            raise ValueError("local deflator base year must come from catalog evidence")
        expected_rejections = _local_deflator_rejection_codes(self)
        if self.rejection_codes != expected_rejections:
            raise ValueError("local deflator rejection codes must be recomputed")
        if self.eligible != (not expected_rejections):
            raise ValueError("local deflator eligibility must derive from rejection codes")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("local deflator projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the local deflator disposition without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class AcceptanceFallbackSelection(_StrictModel):
    """Full-denominator local fallback after the authorized live carrier terminal."""

    schema_version: Literal["policyos.layer3.gy.n13b.acceptance_fallback.v1"] = (
        "policyos.layer3.gy.n13b.acceptance_fallback.v1"
    )
    baseline_ref: str = Field(min_length=1)
    baseline_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    input_selection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    transform_family_id: str = Field(min_length=1)
    transform_family_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    selector_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    live_execution_receipt_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    live_terminal_failure_code: str = Field(min_length=1)
    all_local_series_group_count: int = Field(ge=1)
    non_index_series_group_count: int = Field(ge=0)
    local_index_denominator_count: int = Field(ge=1)
    eligible_local_deflator_count: int = Field(ge=0)
    rejection_counts: dict[str, int]
    local_index_denominator: tuple[LocalDeflatorDisposition, ...] = Field(min_length=1)
    disposition: Literal["local_fallback_admissible", "acceptance_inputs_inadmissible"]
    selected_nominal_projection_sha256: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    selected_deflator: LocalDeflatorDisposition | None
    selected_deflator_points: tuple[LocalDeflatorPoint, ...]
    exact_overlap_years: tuple[int, ...]
    recipe_base_year_selection: str | None = Field(default=None, min_length=1)
    recipe_base_year: int | None = Field(default=None, ge=1900, le=2200)
    deflator_version: str | None
    selection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _selection_is_recomputed(self) -> Self:
        if self.all_local_series_group_count != (
            self.non_index_series_group_count + self.local_index_denominator_count
        ):
            raise ValueError("local deflator denominator must cover every local series group")
        if self.local_index_denominator_count != len(self.local_index_denominator):
            raise ValueError("local index denominator count drift")
        eligible = tuple(row for row in self.local_index_denominator if row.eligible)
        if self.eligible_local_deflator_count != len(eligible):
            raise ValueError("eligible local deflator count drift")
        if self.rejection_counts != _rejection_counts(self.local_index_denominator):
            raise ValueError("local deflator rejection census must be recomputed")
        expected_disposition = (
            "local_fallback_admissible" if eligible else "acceptance_inputs_inadmissible"
        )
        if self.disposition != expected_disposition:
            raise ValueError("local fallback disposition must derive from the denominator")
        optional = (
            self.selected_nominal_projection_sha256,
            self.selected_deflator,
            self.recipe_base_year_selection,
            self.deflator_version,
        )
        if self.recipe_base_year is not None:
            raise ValueError("recipe parameters must be resolved by the derivation owner")
        if eligible and any(value is None for value in optional):
            raise ValueError("admissible fallback requires a complete derivation scope")
        if not eligible and any(value is not None for value in optional):
            raise ValueError("inadmissible fallback cannot select derivation inputs")
        if eligible:
            assert self.selected_deflator is not None
            if self.selected_deflator != min(eligible, key=_local_deflator_rank_key):
                raise ValueError("local deflator selection must use the declared rank")
            if len(self.selected_deflator_points) != self.selected_deflator.distinct_year_count:
                raise ValueError("selected local deflator point denominator drift")
            if (
                _point_projection_sha256(self.selected_deflator_points)
                != self.selected_deflator.observation_projection_sha256
            ):
                raise ValueError("selected local deflator points must bind their observation owner")
            if self.exact_overlap_years != self.selected_deflator.overlapping_nominal_years:
                raise ValueError("fallback exact overlap must derive from the selected deflator")
            if not self.exact_overlap_years:
                raise ValueError("admissible fallback requires at least one exact overlap year")
            versions = {
                (point.dataset_version, point.source_watermark, point.acquisition_method)
                for point in self.selected_deflator_points
            }
            if len(versions) != 1:
                raise ValueError("selected local deflator version must be singular")
            dataset_version, watermark, acquisition_method = next(iter(versions))
            expected_version = (
                f"{self.selected_deflator.source}.{acquisition_method}."
                f"{dataset_version}@{watermark}"
            )
            if self.deflator_version != expected_version:
                raise ValueError(
                    "deflator version must bind source, loader, version, and watermark"
                )
        elif self.selected_deflator_points or self.exact_overlap_years:
            raise ValueError("inadmissible fallback cannot carry selected observations")
        if self.selection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("local fallback selection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the fallback selection without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "selection_sha256"
        }


class ConsumerMethodExecution(_StrictModel):
    """One real method lane consuming the verified cached derivation."""

    consumer_method_id: str = Field(min_length=1)
    consumption: CertifiedDerivationConsumption
    result_projection: dict[str, Any]
    result_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _execution_is_content_bound(self) -> Self:
        if self.consumer_method_id != self.consumption.consumer_method_id:
            raise ValueError("consumer execution method and consumption receipt differ")
        if self.result_sha256 != content_sha256(_json_values(self.result_projection)):
            raise ValueError("consumer result identity must be recomputed")
        return self


class AcceptanceCaseReceipt(_StrictModel):
    """Frozen proof of one derivation, two consumers, reuse, and fail-closed negatives."""

    schema_version: Literal["policyos.layer3.gy.n13b.derived_acceptance.v1"] = (
        "policyos.layer3.gy.n13b.derived_acceptance.v1"
    )
    fallback_selection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    baseline_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_epoch: Literal[0]
    transform_family_id: str = Field(min_length=1)
    transform_family_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    selector_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    primary_input_role: str = Field(min_length=1)
    auxiliary_input_role: str = Field(min_length=1)
    nominal_series_artifact_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    deflator_series_artifact_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    recipe: DerivationRecipe
    certificate: DerivationCertificate
    derived_artifact_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    certificate_artifact_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    first_materialization_cache_hit: Literal[False]
    second_materialization_cache_hit: Literal[True]
    consumers: tuple[ConsumerMethodExecution, ConsumerMethodExecution]
    basis_mismatch_refusal_code: Literal["basis_mismatch"]
    basis_mismatch_refusal_reason: Literal["no_certified_transform"]
    basis_mismatch_detail_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    model_output_observation_rejection_codes: tuple[str, ...]
    disposition: Literal["accepted_local_fallback"]
    receipt_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _receipt_is_recomputed(self) -> Self:
        if self.primary_input_role == self.auxiliary_input_role:
            raise ValueError("acceptance receipt input roles must be distinct")
        role_artifacts = {item.role: str(item.artifact.artifact_id) for item in self.recipe.inputs}
        if set(role_artifacts) != {self.primary_input_role, self.auxiliary_input_role}:
            raise ValueError("acceptance recipe role denominator drift")
        if role_artifacts[self.primary_input_role] != self.nominal_series_artifact_id:
            raise ValueError("acceptance recipe primary input drift")
        if role_artifacts[self.auxiliary_input_role] != self.deflator_series_artifact_id:
            raise ValueError("acceptance recipe auxiliary input drift")
        if (
            self.recipe.family.family_id != self.transform_family_id
            or content_sha256(self.recipe.family.model_dump(mode="json"))
            != self.transform_family_projection_sha256
        ):
            raise ValueError("acceptance transform-family projection drift")
        if self.certificate.recipe != self.recipe:
            raise ValueError("acceptance certificate recipe drift")
        if str(self.certificate.derived_artifact_id) != self.derived_artifact_id:
            raise ValueError("acceptance certificate output drift")
        method_ids = tuple(item.consumer_method_id for item in self.consumers)
        if method_ids != tuple(sorted(set(method_ids))) or len(method_ids) != 2:
            raise ValueError("acceptance case requires two distinct sorted consumer lanes")
        for consumer in self.consumers:
            if (
                str(consumer.consumption.certificate_artifact_id) != self.certificate_artifact_id
                or str(consumer.consumption.derived_artifact_id) != self.derived_artifact_id
                or consumer.consumption.observation_class != "derived"
                or not consumer.consumption.cache_verified
            ):
                raise ValueError("acceptance consumers must bind one verified cached derivation")
        expected_model_rejections = derive_observation_provenance_rejections(
            ObservationProvenanceClass.MODEL_OUTPUT
        )
        if self.model_output_observation_rejection_codes != expected_model_rejections:
            raise ValueError("model-output refusal must come from the admission owner")
        if self.receipt_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("derived acceptance receipt identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the acceptance-case proof without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "receipt_sha256"
        }


@dataclass(frozen=True)
class AcceptanceAuthorityOwners:
    """Byte-stable canonical authority extension and its exact E7 receipt."""

    input_selection: AcceptanceInputSelection
    entry: Any
    family_receipt: Any
    registry: Any
    provision: Any
    owner: AcceptanceAuthorityOwner
    family_receipt_bytes: bytes
    registry_bytes: bytes
    provision_bytes: bytes
    owner_bytes: bytes

    def payloads(self) -> dict[Path, bytes]:
        """Return the canonical owner payloads in repository-relative locations."""

        return {
            DEFAULT_ACCEPTANCE_DEFLATOR_HARNESS: self.family_receipt_bytes,
            DEFAULT_TARGET_AUTHORITY_REGISTRY: self.registry_bytes,
            DEFAULT_TARGET_AUTHORITY_PROVISION: self.provision_bytes,
            DEFAULT_ACCEPTANCE_AUTHORITY_OWNER: self.owner_bytes,
        }


def _load_acceptance_derivation_owner(
    source: Path,
) -> AcceptanceDerivationOwner:
    """Load one narrow acceptance selector and the generic family registry."""

    try:
        catalog_owner = data_forge_read_api.catalog.load_derivation_catalog_selection(source)
        selector = data_forge_read_api.catalog.resolve_catalog_selection_policy(
            catalog_owner,
            purpose="derived_acceptance",
        )
        registry = load_transform_family_registry({"families": catalog_owner.families_payload})
    except (
        OSError,
        ValueError,
        data_forge_read_api.catalog.CatalogSelectionError,
    ) as exc:
        raise AcceptanceSelectionError(
            "acceptance_derivation_registry_unresolved",
            Path(source).as_posix(),
        ) from exc
    matched = tuple(
        family
        for family in registry.families
        if (family.family_id, family.method_version)
        == (selector.family_id, selector.method_version)
    )
    if len(matched) != 1:
        raise AcceptanceSelectionError("acceptance_derivation_family_unresolved")
    family = matched[0]
    roles = {spec.role for spec in family.input_specs}
    selector_roles = {item.role for item in selector.roles}
    if roles != selector_roles or len(roles) != 2:
        raise AcceptanceSelectionError(
            "acceptance_derivation_role_contract_drift", selector.family_id
        )
    template_fields = {
        field_name
        for _, field_name, _, _ in Formatter().parse(selector.output_variable_id_template)
        if field_name is not None
    }
    allowed_template_fields = {
        *(f"{role}_canonical_variable" for role in roles),
        *(rule.name for rule in family.parameter_rules),
    }
    primary_field = f"{family.year_domain_role}_canonical_variable"
    if primary_field not in template_fields or not template_fields.issubset(
        allowed_template_fields
    ):
        raise AcceptanceSelectionError(
            "acceptance_output_variable_template_unresolved",
            selector.output_variable_id_template,
        )
    return AcceptanceDerivationOwner(
        registry=registry,
        family=family,
        selector=selector,
    )


def _family_input_spec(
    owner: AcceptanceDerivationOwner,
    role: str,
) -> TransformInputSpec:
    return next(spec for spec in owner.family.input_specs if spec.role == role)


def _catalog_role_policy(
    owner: AcceptanceDerivationOwner,
    *,
    role: str,
) -> CatalogSelectionRoleConfig:
    return owner.selection_role(role)


def derive_acceptance_input_selection(
    *,
    catalog_path: Path,
    census_path: Path,
    r1_paid_success_elapsed_seconds: float,
    family_registry_path: Path = DEFAULT_DERIVATION_FAMILY_REGISTRY,
) -> AcceptanceInputSelection:
    """Recompute the complete local nominal and live deflator denominators."""

    catalog = Path(catalog_path)
    derivation_owner = _load_acceptance_derivation_owner(family_registry_path)
    census_file = Path(census_path)
    if not catalog.is_file():
        raise AcceptanceSelectionError("acceptance_catalog_unresolved", catalog.as_posix())
    try:
        census = json.loads(census_file.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceptanceSelectionError(
            "acceptance_census_unresolved", census_file.as_posix()
        ) from exc
    if not isinstance(census, Mapping):
        raise AcceptanceSelectionError("acceptance_census_invalid")
    live_families, family_projection = _live_families(census)
    primary_policy = _catalog_role_policy(
        derivation_owner,
        role=derivation_owner.primary_role,
    )
    auxiliary_policy = _catalog_role_policy(
        derivation_owner,
        role=derivation_owner.auxiliary_role,
    )
    local_rows, local_points, all_local_groups = _read_local_denominator(
        catalog,
        expected_unit=primary_policy.catalog_unit,
        country_code=derivation_owner.selector.country_code,
    )
    deflator_rows = _read_deflator_denominator(
        catalog,
        metric_id=auxiliary_policy.owner_metric_id,
    )

    local_dispositions = tuple(
        _build_local_disposition(
            row,
            points=local_points[row["series_key"]],
            role_policy=primary_policy,
        )
        for row in local_rows
    )
    deflator_dispositions = tuple(
        _build_deflator_disposition(
            row,
            live_families=live_families,
            role_policy=auxiliary_policy,
        )
        for row in deflator_rows
    )
    eligible_local = tuple(row for row in local_dispositions if row.eligible)
    eligible_deflators = tuple(row for row in deflator_dispositions if row.eligible)
    selected_nominal = min(eligible_local, key=_local_rank_key) if eligible_local else None
    selected_deflator = (
        min(eligible_deflators, key=_deflator_rank_key) if eligible_deflators else None
    )
    selected_points: tuple[LocalNominalPoint, ...] = ()
    execution_selection: LiveTargetSelection | None = None
    request_start_year: int | None = None
    request_end_year: int | None = None
    request_page_size: int | None = None
    pair_selected = selected_nominal is not None and selected_deflator is not None
    if pair_selected:
        assert selected_nominal is not None
        assert selected_deflator is not None
        selected_points = tuple(
            LocalNominalPoint.model_validate(point)
            for point in local_points[
                (
                    selected_nominal.dataset_id,
                    selected_nominal.raw_variable,
                    selected_nominal.canonical_variable,
                )
            ]
        )
        request_start_year = min(
            selected_points[0].year,
            selected_deflator.reference_base_year or selected_points[0].year,
        )
        request_end_year = selected_points[-1].year
        request_page_size = request_end_year - request_start_year + 1
        execution_selection = _execution_selection(
            selected_deflator,
            live_families=live_families,
            catalog_denominator_count=len(deflator_dispositions),
            eligible_count=len(eligible_deflators),
            decisive_rejections=_decisive_rejection_counts(deflator_dispositions),
        )

    baseline_sha = _file_sha256(catalog)
    timeout_cap = float(__import__("math").ceil(float(r1_paid_success_elapsed_seconds) * 2))
    values: dict[str, object] = {
        "schema_version": "policyos.layer3.gy.n13b.acceptance_inputs.v1",
        "baseline_ref": _stable_repo_ref(catalog),
        "baseline_sha256": baseline_sha,
        "census_family_projection_sha256": content_sha256(family_projection),
        "transform_family_id": derivation_owner.family.family_id,
        "transform_family_projection_sha256": (derivation_owner.family_projection_sha256),
        "selector_projection_sha256": derivation_owner.selector_projection_sha256,
        "primary_input_role": derivation_owner.primary_role,
        "auxiliary_input_role": derivation_owner.auxiliary_role,
        "country_code": derivation_owner.selector.country_code,
        "all_local_series_group_count": all_local_groups,
        "non_monetary_series_group_count": all_local_groups - len(local_dispositions),
        "local_monetary_denominator_count": len(local_dispositions),
        "eligible_local_nominal_count": len(eligible_local),
        "local_rejection_counts": _rejection_counts(local_dispositions),
        "local_monetary_denominator": local_dispositions,
        "inflation_binding_denominator_count": len(deflator_dispositions),
        "eligible_deflator_count": len(eligible_deflators),
        "deflator_rejection_counts": _rejection_counts(deflator_dispositions),
        "deflator_denominator": deflator_dispositions,
        "disposition": ("admissible_pair" if pair_selected else "acceptance_inputs_inadmissible"),
        "selected_nominal": selected_nominal if pair_selected else None,
        "selected_nominal_points": selected_points,
        "selected_deflator": selected_deflator if pair_selected else None,
        "execution_selection": execution_selection,
        "request_start_year": request_start_year,
        "request_end_year": request_end_year,
        "request_page_size": request_page_size,
        "paid_success_elapsed_seconds": float(r1_paid_success_elapsed_seconds),
        "timeout_multiplier": 2,
        "derived_timeout_cap_seconds": timeout_cap,
    }
    return AcceptanceInputSelection(
        **values,
        selection_sha256=content_sha256(_json_values(values)),
    )


def derive_acceptance_authority_owners(
    selection: AcceptanceInputSelection,
    *,
    base_owners: Any,
    catalog_path: Path,
    baseline_owner_ref: str,
    l5_path: Path,
    l5_owner_ref: str,
    fixture_root: Path,
) -> AcceptanceAuthorityOwners:
    """Extend the canonical registry/provision with one exact live carrier."""

    selected = AcceptanceInputSelection.model_validate(selection.model_dump(mode="python"))
    if selected.disposition != "admissible_pair" or selected.execution_selection is None:
        raise AcceptanceSelectionError("acceptance_authority_inputs_inadmissible")
    base_entries = tuple(base_owners.registry.entries)
    if not base_entries:
        raise AcceptanceSelectionError("acceptance_base_authority_empty")
    receipt = derive_target_family_receipt(
        selected.execution_selection,
        catalog_path=Path(catalog_path),
        fixture_root=Path(fixture_root),
    )
    single = derive_target_authority_owners(
        selected.execution_selection,
        family_receipt=receipt,
        baseline_path=Path(catalog_path),
        baseline_owner_ref=baseline_owner_ref,
        l5_path=Path(l5_path),
        l5_owner_ref=l5_owner_ref,
        receipt_owner_ref=f"repo://{DEFAULT_ACCEPTANCE_DEFLATOR_HARNESS.as_posix()}",
        country_codes=("UKR",),
    )
    if single.entry.entry_id in {entry.entry_id for entry in base_entries}:
        raise AcceptanceSelectionError("acceptance_authority_entry_collision")
    baseline_sha = _file_sha256(Path(catalog_path))
    l5_sha = _file_sha256(Path(l5_path))
    if (
        base_owners.registry.baseline_content_sha256 != baseline_sha
        or base_owners.registry.l5_measurement_registry_sha256 != l5_sha
    ):
        raise AcceptanceSelectionError("acceptance_base_authority_owner_drift")
    registry = data_forge_read_api.catalog.build_authority_registry(
        baseline_content_sha256=baseline_sha,
        l5_measurement_registry_sha256=l5_sha,
        entries=(*base_entries, single.entry),
    )
    family_receipt_bytes = canonical_json_bytes(receipt.model_dump(mode="json"))
    live_receipts = [
        item.model_dump(mode="json") for item in base_owners.provision.live_harness_receipts
    ]
    live_receipts.append(
        {
            "entry_id": single.entry.entry_id,
            "attempt_id": derive_live_attempt_id(selected.execution_selection),
            "receipt_owner_ref": (f"repo://{DEFAULT_ACCEPTANCE_DEFLATOR_HARNESS.as_posix()}"),
            "receipt_content_sha256": bytes_sha256(family_receipt_bytes),
        }
    )
    live_receipts.sort(key=lambda item: (str(item["attempt_id"]), str(item["entry_id"])))
    provision = data_forge_read_api.catalog.build_acquisition_authority_provision(
        baseline_owner_ref=baseline_owner_ref,
        baseline_content_sha256=baseline_sha,
        l5_measurement_registry_owner_ref=l5_owner_ref,
        l5_measurement_registry_content_sha256=l5_sha,
        live_harness_receipts=tuple(live_receipts),
    )
    selection_bytes = canonical_json_bytes(selected.model_dump(mode="json"))
    owner_values: dict[str, object] = {
        "schema_version": "policyos.layer3.gy.n13b.acceptance_authority.v1",
        "input_selection_sha256": selected.selection_sha256,
        "input_selection_file_sha256": bytes_sha256(selection_bytes),
        "baseline_sha256": baseline_sha,
        "l5_measurement_registry_sha256": l5_sha,
        "authority_entry_id": single.entry.entry_id,
        "live_attempt_id": derive_live_attempt_id(selected.execution_selection),
        "live_harness_content_sha256": bytes_sha256(family_receipt_bytes),
        "combined_registry_content_sha256": registry.content_sha256,
        "combined_provision_id": provision.provision_id,
        "registry_entry_count": len(registry.entries),
        "live_harness_receipt_count": len(provision.live_harness_receipts),
    }
    owner = AcceptanceAuthorityOwner(
        **owner_values,
        owner_sha256=content_sha256(owner_values),
    )
    return AcceptanceAuthorityOwners(
        input_selection=selected,
        entry=single.entry,
        family_receipt=receipt,
        registry=registry,
        provision=provision,
        owner=owner,
        family_receipt_bytes=family_receipt_bytes,
        registry_bytes=canonical_json_bytes(registry.model_dump(mode="json")),
        provision_bytes=canonical_json_bytes(provision.model_dump(mode="json")),
        owner_bytes=canonical_json_bytes(owner.model_dump(mode="json")),
    )


def derive_acceptance_live_execution_receipt(
    *,
    selection: AcceptanceInputSelection,
    authority_owner: AcceptanceAuthorityOwner,
    journal_path: Path,
    baseline_path: Path,
    live_source_execution: Any | None,
) -> AcceptanceLiveExecutionReceipt:
    """Reopen the exact one-call journal outcome and bind optional Fabric evidence."""

    selected = AcceptanceInputSelection.model_validate(selection.model_dump(mode="python"))
    owner = AcceptanceAuthorityOwner.model_validate(authority_owner.model_dump(mode="python"))
    if selected.execution_selection is None:
        raise AcceptanceSelectionError("acceptance_execution_selection_missing")
    attempt_id = derive_live_attempt_id(selected.execution_selection)
    if owner.live_attempt_id != attempt_id:
        raise AcceptanceSelectionError("acceptance_execution_authority_drift")
    terminals = resolve_live_attempt_terminals(Path(journal_path))
    matches = tuple(terminal for terminal in terminals if terminal.attempt_id == attempt_id)
    if len(matches) != 1:
        raise AcceptanceSelectionError(
            "acceptance_live_terminal_unresolved",
            attempt_id,
        )
    terminal = matches[0]
    call_count = _journal_transport_call_count(Path(journal_path), attempt_id=attempt_id)
    baseline_sha = _file_sha256(Path(baseline_path))
    evidence: Any | None = None
    disposition: Literal["measured_pending_passport", "live_execution_terminal"]
    if live_source_execution is None:
        disposition = "live_execution_terminal"
    else:
        evidence = data_forge_read_api.catalog.LiveSourceExecutionEvidence.model_validate(
            live_source_execution
        )
        disposition = "measured_pending_passport"
    values: dict[str, object] = {
        "schema_version": "policyos.layer3.gy.n13b.acceptance_live_execution.v1",
        "input_selection_sha256": selected.selection_sha256,
        "authority_owner_sha256": owner.owner_sha256,
        "attempt_id": attempt_id,
        "disposition": disposition,
        "call_count": call_count,
        "terminal": terminal,
        "live_source_execution": evidence,
        "baseline_before_sha256": selected.baseline_sha256,
        "baseline_after_sha256": baseline_sha,
    }
    return AcceptanceLiveExecutionReceipt(
        **values,
        receipt_sha256=content_sha256(_json_values(values)),
    )


def derive_acceptance_fallback_selection(
    *,
    input_selection: AcceptanceInputSelection,
    live_execution: AcceptanceLiveExecutionReceipt,
    catalog_path: Path,
    family_registry_path: Path = DEFAULT_DERIVATION_FAMILY_REGISTRY,
) -> AcceptanceFallbackSelection:
    """Recompute every local index series after the one authorized live terminal."""

    selected = AcceptanceInputSelection.model_validate(input_selection.model_dump(mode="python"))
    live = AcceptanceLiveExecutionReceipt.model_validate(live_execution.model_dump(mode="python"))
    derivation_owner = _load_acceptance_derivation_owner(family_registry_path)
    if (
        selected.transform_family_id != derivation_owner.family.family_id
        or selected.transform_family_projection_sha256 != derivation_owner.family_projection_sha256
        or selected.selector_projection_sha256 != derivation_owner.selector_projection_sha256
        or selected.primary_input_role != derivation_owner.primary_role
        or selected.auxiliary_input_role != derivation_owner.auxiliary_role
    ):
        raise AcceptanceSelectionError("acceptance_fallback_derivation_owner_drift")
    if selected.selected_nominal is None or not selected.selected_nominal_points:
        raise AcceptanceSelectionError("acceptance_fallback_nominal_input_missing")
    if (
        live.input_selection_sha256 != selected.selection_sha256
        or live.baseline_after_sha256 != selected.baseline_sha256
    ):
        raise AcceptanceSelectionError("acceptance_fallback_live_receipt_drift")
    if live.disposition != "live_execution_terminal" or live.live_source_execution is not None:
        raise AcceptanceSelectionError("acceptance_fallback_requires_live_terminal")
    catalog = Path(catalog_path)
    if _file_sha256(catalog) != selected.baseline_sha256:
        raise AcceptanceSelectionError("acceptance_fallback_baseline_drift")

    auxiliary_policy = _catalog_role_policy(
        derivation_owner,
        role=derivation_owner.auxiliary_role,
    )
    nominal_years = tuple(point.year for point in selected.selected_nominal_points)
    rows, points, all_local_groups = _read_local_index_denominator(
        catalog,
        expected_unit=auxiliary_policy.catalog_unit,
        country_code=derivation_owner.selector.country_code,
    )
    dispositions = tuple(
        _build_local_deflator_disposition(
            row,
            points=points[row["series_key"]],
            nominal_years=nominal_years,
            role_policy=auxiliary_policy,
        )
        for row in rows
    )
    eligible = tuple(row for row in dispositions if row.eligible)
    selected_deflator = min(eligible, key=_local_deflator_rank_key) if eligible else None
    selected_points: tuple[LocalDeflatorPoint, ...] = ()
    exact_overlap_years: tuple[int, ...] = ()
    parameter_rule_selection: str | None = None
    deflator_version: str | None = None
    if selected_deflator is not None:
        selected_points = tuple(
            LocalDeflatorPoint.model_validate(point)
            for point in points[
                (
                    selected_deflator.dataset_id,
                    selected_deflator.raw_variable,
                    selected_deflator.canonical_variable,
                )
            ]
        )
        exact_overlap_years = selected_deflator.overlapping_nominal_years
        rules = tuple(
            rule
            for rule in derivation_owner.family.parameter_rules
            if set(rule.input_roles)
            == {
                derivation_owner.primary_role,
                derivation_owner.auxiliary_role,
            }
        )
        if len(rules) != 1:
            raise AcceptanceSelectionError(
                "acceptance_family_parameter_rule_unresolved",
                derivation_owner.family.family_id,
            )
        parameter_rule_selection = rules[0].operator
        versions = {
            (point.dataset_version, point.source_watermark, point.acquisition_method)
            for point in selected_points
        }
        if len(versions) != 1:
            raise AcceptanceSelectionError("acceptance_fallback_deflator_version_ambiguous")
        dataset_version, watermark, acquisition_method = next(iter(versions))
        deflator_version = (
            f"{selected_deflator.source}.{acquisition_method}.{dataset_version}@{watermark}"
        )
    values: dict[str, object] = {
        "schema_version": "policyos.layer3.gy.n13b.acceptance_fallback.v1",
        "baseline_ref": selected.baseline_ref,
        "baseline_sha256": selected.baseline_sha256,
        "input_selection_sha256": selected.selection_sha256,
        "transform_family_id": derivation_owner.family.family_id,
        "transform_family_projection_sha256": (derivation_owner.family_projection_sha256),
        "selector_projection_sha256": derivation_owner.selector_projection_sha256,
        "live_execution_receipt_sha256": live.receipt_sha256,
        "live_terminal_failure_code": live.terminal.failure_code,
        "all_local_series_group_count": all_local_groups,
        "non_index_series_group_count": all_local_groups - len(dispositions),
        "local_index_denominator_count": len(dispositions),
        "eligible_local_deflator_count": len(eligible),
        "rejection_counts": _rejection_counts(dispositions),
        "local_index_denominator": dispositions,
        "disposition": (
            "local_fallback_admissible"
            if selected_deflator is not None
            else "acceptance_inputs_inadmissible"
        ),
        "selected_nominal_projection_sha256": (
            selected.selected_nominal.projection_sha256 if selected_deflator is not None else None
        ),
        "selected_deflator": selected_deflator,
        "selected_deflator_points": selected_points,
        "exact_overlap_years": exact_overlap_years,
        "recipe_base_year_selection": parameter_rule_selection,
        "recipe_base_year": None,
        "deflator_version": deflator_version,
    }
    return AcceptanceFallbackSelection(
        **values,
        selection_sha256=content_sha256(_json_values(values)),
    )


def materialize_acceptance_case(
    *,
    input_selection: AcceptanceInputSelection,
    fallback_selection: AcceptanceFallbackSelection,
    store: artifacts.FileSystemCAS,
    require_first_cache_miss: bool = True,
    family_registry_path: Path = DEFAULT_DERIVATION_FAMILY_REGISTRY,
) -> AcceptanceCaseReceipt:
    """Materialize and consume the certified local-fallback derivation once."""

    selected = AcceptanceInputSelection.model_validate(input_selection.model_dump(mode="python"))
    fallback = AcceptanceFallbackSelection.model_validate(
        fallback_selection.model_dump(mode="python")
    )
    derivation_owner = _load_acceptance_derivation_owner(family_registry_path)
    if (
        fallback.input_selection_sha256 != selected.selection_sha256
        or fallback.disposition != "local_fallback_admissible"
        or selected.selected_nominal is None
        or fallback.selected_deflator is None
        or fallback.deflator_version is None
    ):
        raise AcceptanceSelectionError("acceptance_case_inputs_inadmissible")
    if (
        selected.transform_family_id != derivation_owner.family.family_id
        or selected.transform_family_projection_sha256 != derivation_owner.family_projection_sha256
        or selected.selector_projection_sha256 != derivation_owner.selector_projection_sha256
        or fallback.transform_family_id != derivation_owner.family.family_id
        or fallback.transform_family_projection_sha256 != derivation_owner.family_projection_sha256
        or fallback.selector_projection_sha256 != derivation_owner.selector_projection_sha256
    ):
        raise AcceptanceSelectionError("acceptance_case_derivation_owner_drift")

    primary_role = derivation_owner.primary_role
    auxiliary_role = derivation_owner.auxiliary_role
    primary_spec = _family_input_spec(derivation_owner, primary_role)
    auxiliary_spec = _family_input_spec(derivation_owner, auxiliary_role)

    primary_authority = _persist_input_authority(
        store,
        role=primary_role,
        baseline_sha256=fallback.baseline_sha256,
        disposition_payload=selected.selected_nominal.identity_payload(),
        observation_projection_sha256=(selected.selected_nominal.observation_projection_sha256),
        alignment_confidence=selected.selected_nominal.alignment_confidence,
        binding_confidence=selected.selected_nominal.maximum_binding_confidence,
        distribution_quality=selected.selected_nominal.maximum_distribution_quality,
    )
    auxiliary_authority = _persist_input_authority(
        store,
        role=auxiliary_role,
        baseline_sha256=fallback.baseline_sha256,
        disposition_payload=fallback.selected_deflator.identity_payload(),
        observation_projection_sha256=(fallback.selected_deflator.observation_projection_sha256),
        alignment_confidence=fallback.selected_deflator.alignment_confidence,
        binding_confidence=fallback.selected_deflator.maximum_binding_confidence,
        distribution_quality=fallback.selected_deflator.maximum_distribution_quality,
    )
    primary_series = SourceSeries(
        variable_id=selected.selected_nominal.canonical_variable,
        basis=primary_spec.basis,
        points=tuple(
            SeriesPoint(year=point.year, value=point.value)
            for point in selected.selected_nominal_points
        ),
        authority=primary_authority,
        observation_class="observed",
    )
    auxiliary_series = SourceSeries(
        variable_id=fallback.selected_deflator.canonical_variable,
        basis=auxiliary_spec.basis,
        points=tuple(
            SeriesPoint(year=point.year, value=point.value)
            for point in fallback.selected_deflator_points
        ),
        authority=auxiliary_authority,
        observation_class="observed",
    )
    primary_ref = persist_source_series(
        store,
        primary_series,
    )
    auxiliary_ref = persist_source_series(
        store,
        auxiliary_series,
    )
    input_refs = {
        primary_role: primary_ref,
        auxiliary_role: auxiliary_ref,
    }
    preview = build_derivation_recipe(
        store,
        registry=derivation_owner.registry,
        input_refs=input_refs,
        output_variable_id=f"{selected.selected_nominal.canonical_variable}.preview",
        family_id=derivation_owner.family.family_id,
    )
    if fallback.recipe_base_year_selection not in {
        parameter.rule.operator for parameter in preview.parameters
    }:
        raise AcceptanceSelectionError("acceptance_recipe_parameter_rule_drift")
    variable_context = {
        f"{primary_role}_canonical_variable": selected.selected_nominal.canonical_variable,
        f"{auxiliary_role}_canonical_variable": (fallback.selected_deflator.canonical_variable),
        **{parameter.name: format(parameter.value, "f") for parameter in preview.parameters},
    }
    try:
        output_variable_id = derivation_owner.selector.output_variable_id_template.format_map(
            variable_context
        )
    except (KeyError, ValueError) as exc:
        raise AcceptanceSelectionError("acceptance_output_variable_template_unresolved") from exc
    recipe = build_derivation_recipe(
        store,
        registry=derivation_owner.registry,
        input_refs=input_refs,
        output_variable_id=output_variable_id,
        family_id=derivation_owner.family.family_id,
    )
    first = materialize_derivation(store, recipe)
    if require_first_cache_miss and first.cache_hit:
        raise AcceptanceSelectionError("acceptance_first_materialization_not_cache_miss")
    second = materialize_derivation(store, recipe)
    if not second.cache_hit:
        raise AcceptanceSelectionError("acceptance_second_materialization_not_cache_hit")
    if (
        first.derived_artifact_ref != second.derived_artifact_ref
        or first.certificate_artifact_ref != second.certificate_artifact_ref
    ):
        raise AcceptanceSelectionError("acceptance_cache_identity_drift")

    consumer_executions = _consume_acceptance_methods(
        store,
        certificate_ref=second.certificate_artifact_ref,
    )
    try:
        mismatched_basis_payload = recipe.output_basis.model_dump(mode="python")
        mismatched_basis_payload["unit"] = f"{recipe.output_basis.unit}.uncertified"
        build_derivation_recipe(
            store,
            registry=derivation_owner.registry,
            input_refs=input_refs,
            output_variable_id=output_variable_id,
            output_basis=BasisSignature.model_validate(mismatched_basis_payload),
        )
    except DerivationRefusalError as exc:
        if (
            exc.code is not DerivationRefusalCode.BASIS_MISMATCH
            or exc.reason is not DerivationRefusalReason.NO_CERTIFIED_TRANSFORM
        ):
            raise
        basis_mismatch_detail_sha256 = content_sha256(
            {
                "code": exc.code.value,
                "reason": exc.reason.value,
                "detail": exc.detail,
            }
        )
    else:
        raise AcceptanceSelectionError("acceptance_basis_mismatch_did_not_refuse")

    values: dict[str, object] = {
        "schema_version": "policyos.layer3.gy.n13b.derived_acceptance.v1",
        "fallback_selection_sha256": fallback.selection_sha256,
        "baseline_sha256": fallback.baseline_sha256,
        "source_epoch": 0,
        "transform_family_id": derivation_owner.family.family_id,
        "transform_family_projection_sha256": (derivation_owner.family_projection_sha256),
        "selector_projection_sha256": derivation_owner.selector_projection_sha256,
        "primary_input_role": primary_role,
        "auxiliary_input_role": auxiliary_role,
        "nominal_series_artifact_id": str(primary_ref.artifact_id),
        "deflator_series_artifact_id": str(auxiliary_ref.artifact_id),
        "recipe": recipe,
        "certificate": second.certificate,
        "derived_artifact_id": str(second.derived_artifact_ref.artifact_id),
        "certificate_artifact_id": str(second.certificate_artifact_ref.artifact_id),
        "first_materialization_cache_hit": False,
        "second_materialization_cache_hit": True,
        "consumers": consumer_executions,
        "basis_mismatch_refusal_code": DerivationRefusalCode.BASIS_MISMATCH.value,
        "basis_mismatch_refusal_reason": (DerivationRefusalReason.NO_CERTIFIED_TRANSFORM.value),
        "basis_mismatch_detail_sha256": basis_mismatch_detail_sha256,
        "model_output_observation_rejection_codes": (
            derive_observation_provenance_rejections(ObservationProvenanceClass.MODEL_OUTPUT)
        ),
        "disposition": "accepted_local_fallback",
    }
    return AcceptanceCaseReceipt(
        **values,
        receipt_sha256=content_sha256(_json_values(values)),
    )


def verify_persisted_acceptance_case(
    store: artifacts.FileSystemCAS,
    receipt: AcceptanceCaseReceipt,
) -> None:
    """Reopen every durable acceptance artifact and rerun both consumers."""

    frozen = AcceptanceCaseReceipt.model_validate(receipt.model_dump(mode="python"))
    for artifact_id in (
        frozen.nominal_series_artifact_id,
        frozen.deflator_series_artifact_id,
        frozen.derived_artifact_id,
        frozen.certificate_artifact_id,
    ):
        parsed = artifacts.ArtifactID.model_validate(artifact_id)
        if not store.has(parsed) or not store.verify(parsed).ok:
            raise AcceptanceSelectionError("acceptance_persisted_artifact_drift", artifact_id)
    certificate_ref = artifacts.ArtifactRef(
        artifact_id=artifacts.ArtifactID.model_validate(frozen.certificate_artifact_id),
        kind=DERIVATION_CERTIFICATE_KIND,
        media_type="application/json",
    )
    current = _consume_acceptance_methods(store, certificate_ref=certificate_ref)
    if current != frozen.consumers:
        raise AcceptanceSelectionError("acceptance_persisted_consumer_drift")


def _persist_input_authority(
    store: artifacts.FileSystemCAS,
    *,
    role: str,
    baseline_sha256: str,
    disposition_payload: Mapping[str, object],
    observation_projection_sha256: str,
    alignment_confidence: float | None,
    binding_confidence: float | None,
    distribution_quality: float | None,
) -> AuthorityProjection:
    scores = tuple(
        value
        for value in (alignment_confidence, binding_confidence, distribution_quality)
        if value is not None
    )
    if len(scores) != 3:
        raise AcceptanceSelectionError("acceptance_input_authority_score_missing", role)
    effective_score = min(scores)
    authority_payload = {
        "schema_version": "policyos.layer3.gy.n13b.series_input_authority.v1",
        "role": role,
        "baseline_sha256": baseline_sha256,
        "observation_projection_sha256": observation_projection_sha256,
        "alignment_confidence": alignment_confidence,
        "binding_confidence": binding_confidence,
        "distribution_quality": distribution_quality,
        "effective_score": effective_score,
        "disposition_projection_sha256": content_sha256(disposition_payload),
    }
    verifier_payload = {
        "schema_version": "policyos.layer3.gy.n13b.series_input_verifier.v1",
        "role": role,
        "baseline_sha256": baseline_sha256,
        "observation_projection_sha256": observation_projection_sha256,
        "decisive_checks": (
            "alignment_owner_resolved",
            "binding_owner_resolved",
            "license_owner_admissible",
            "source_watermark_complete",
        ),
        "authority_projection_sha256": content_sha256(authority_payload),
    }
    options = artifacts.PutOptions(
        kind="policyos.layer3.gy.n13b.series_input_evidence",
        media_type="application/json",
        schema=_ACCEPTANCE_EVIDENCE_SCHEMA,
        producer=_ACCEPTANCE_PRODUCER,
    )
    authority_ref = store.put_bytes(canonical_json_bytes(authority_payload), options)
    verifier_ref = store.put_bytes(canonical_json_bytes(verifier_payload), options)
    return AuthorityProjection(
        effective_score=Decimal(str(effective_score)),
        authority_ref=authority_ref.artifact_id,
        verifier_provenance_ref=verifier_ref.artifact_id,
        authoritative_for="series_input",
    )


def _consume_acceptance_methods(
    store: artifacts.FileSystemCAS,
    *,
    certificate_ref: artifacts.ArtifactRef,
) -> tuple[ConsumerMethodExecution, ConsumerMethodExecution]:
    methods = (
        (
            "forecasting.univariate.exponential_smoothing@1.0.0",
            ExponentialSmoothingEstimator,
        ),
        ("forecasting.univariate.theta@1.0.0", ThetaMethodEstimator),
    )
    executions: list[ConsumerMethodExecution] = []
    for method_id, estimator in methods:
        consumption = consume_certified_derivation(
            store,
            certificate_ref=certificate_ref,
            consumer_method_id=method_id,
        )
        result = estimator.pure_step(
            {"series": [float(value) for value in consumption.series]},
            {"horizon": 1},
        )
        # Method owners emit wall-clock diagnostics alongside the deterministic
        # forecast.  The receipt binds the narrow method-result projection so
        # timestamps remain outside content identity.
        projection = {"result": _json_values(result["result"])}
        executions.append(
            ConsumerMethodExecution(
                consumer_method_id=method_id,
                consumption=consumption,
                result_projection=projection,
                result_sha256=content_sha256(projection),
            )
        )
    executions.sort(key=lambda item: item.consumer_method_id)
    return (executions[0], executions[1])


def _read_local_denominator(
    catalog_path: Path,
    *,
    expected_unit: str,
    country_code: str,
) -> tuple[
    tuple[dict[str, object], ...],
    dict[tuple[str, str, str], tuple[dict[str, object], ...]],
    int,
]:
    with duckdb.connect(str(catalog_path), read_only=True) as con:
        rows = con.execute(
            """
            WITH observation_groups AS (
              SELECT o.dataset_id, d.source, d.agency, d.title,
                     coalesce(d.description, '') AS description,
                     coalesce(nullif(d.access_license, ''), d.license, '') AS access_license,
                     o.raw_variable, o.canonical_var,
                     count(*) AS row_count,
                     count(DISTINCT o.year) AS distinct_year_count,
                     min(o.year) AS minimum_year,
                     max(o.year) AS maximum_year,
                     count(*) - count(DISTINCT o.year) AS duplicate_year_count,
                     count(o.source_watermark) AS source_watermark_count,
                     count(o.dataset_version) AS dataset_version_count,
                     count(o.acquisition_method) AS acquisition_method_count
              FROM ds_observations o
              JOIN ds_datasets d ON d.id = o.dataset_id
              WHERE o.country_code = ?
                AND o.value IS NOT NULL
                AND o.year IS NOT NULL
              GROUP BY ALL
            ), exact_bindings AS (
              SELECT b.dataset_id, b.request_dataset_id AS raw_variable,
                     b.metric_id AS canonical_var,
                     count(DISTINCT b.distribution_id) AS exact_binding_count,
                     max(b.confidence) AS maximum_binding_confidence,
                     max(x.quality_score) AS maximum_distribution_quality
              FROM ds_metric_bindings b
              JOIN ds_distributions x ON x.id = b.distribution_id
              GROUP BY b.dataset_id, b.request_dataset_id, b.metric_id
            )
            SELECT o.dataset_id, o.source, o.agency, o.title, o.description,
                   o.access_license, o.raw_variable, o.canonical_var,
                   o.row_count, o.distinct_year_count, o.minimum_year,
                   o.maximum_year, o.duplicate_year_count,
                   o.source_watermark_count, o.dataset_version_count,
                   o.acquisition_method_count,
                   a.method, a.confidence, a.is_proxy, a.proxy_penalty,
                   coalesce(b.exact_binding_count, 0),
                   b.canonical_var,
                   b.maximum_binding_confidence,
                   b.maximum_distribution_quality
            FROM observation_groups o
            LEFT JOIN ds_variable_alignments a
              ON a.dataset_id = o.dataset_id
             AND a.raw_variable = o.raw_variable
             AND a.canonical_var = o.canonical_var
            LEFT JOIN exact_bindings b
              ON b.dataset_id = o.dataset_id
             AND b.raw_variable = o.raw_variable
             AND b.canonical_var = o.canonical_var
            ORDER BY o.dataset_id, o.raw_variable, o.canonical_var
            """,
            [country_code],
        ).fetchall()
        fields = (
            "dataset_id",
            "source",
            "agency",
            "title",
            "description",
            "access_license",
            "raw_variable",
            "canonical_variable",
            "row_count",
            "distinct_year_count",
            "minimum_year",
            "maximum_year",
            "duplicate_year_count",
            "source_watermark_count",
            "dataset_version_count",
            "acquisition_method_count",
            "alignment_method",
            "alignment_confidence",
            "alignment_is_proxy",
            "alignment_proxy_penalty",
            "exact_binding_count",
            "metric_id",
            "maximum_binding_confidence",
            "maximum_distribution_quality",
        )
        all_rows = tuple(dict(zip(fields, row, strict=True)) for row in rows)
        monetary_rows = tuple(
            row
            for row in all_rows
            if data_forge_read_api.catalog.derive_catalog_unit_from_text(
                f"{row['title']} {row['description']}"
            )
            == expected_unit
        )
        points: dict[tuple[str, str, str], tuple[dict[str, object], ...]] = {}
        for row in monetary_rows:
            key = (
                str(row["dataset_id"]),
                str(row["raw_variable"]),
                str(row["canonical_variable"]),
            )
            point_rows = con.execute(
                """
                SELECT observation_id, year, value, source_watermark,
                       dataset_version, acquisition_method
                FROM ds_observations
                WHERE dataset_id = ? AND raw_variable = ? AND canonical_var = ?
                  AND country_code = ? AND value IS NOT NULL AND year IS NOT NULL
                ORDER BY year, observation_id
                """,
                [*key, country_code],
            ).fetchall()
            point_fields = (
                "observation_id",
                "year",
                "value",
                "source_watermark",
                "dataset_version",
                "acquisition_method",
            )
            points[key] = tuple(dict(zip(point_fields, point, strict=True)) for point in point_rows)
            row["series_key"] = key
    return monetary_rows, points, len(all_rows)


def _read_local_index_denominator(
    catalog_path: Path,
    *,
    expected_unit: str,
    country_code: str,
) -> tuple[
    tuple[dict[str, object], ...],
    dict[tuple[str, str, str], tuple[dict[str, object], ...]],
    int,
]:
    with duckdb.connect(str(catalog_path), read_only=True) as con:
        rows = con.execute(
            """
            WITH observation_groups AS (
              SELECT o.dataset_id, d.source, d.agency, d.title,
                     coalesce(d.description, '') AS description,
                     coalesce(nullif(d.access_license, ''), d.license, '') AS access_license,
                     o.raw_variable, o.canonical_var,
                     count(*) AS row_count,
                     count(DISTINCT o.year) AS distinct_year_count,
                     min(o.year) AS minimum_year,
                     max(o.year) AS maximum_year,
                     count(*) - count(DISTINCT o.year) AS duplicate_year_count,
                     count(o.source_watermark) AS source_watermark_count,
                     count(o.dataset_version) AS dataset_version_count,
                     count(o.acquisition_method) AS acquisition_method_count,
                     sum(CASE WHEN o.value <= 0 THEN 1 ELSE 0 END) AS nonpositive_value_count
              FROM ds_observations o
              JOIN ds_datasets d ON d.id = o.dataset_id
              WHERE o.country_code = ?
                AND o.value IS NOT NULL
                AND o.year IS NOT NULL
              GROUP BY ALL
            ), exact_bindings AS (
              SELECT b.dataset_id, b.request_dataset_id AS raw_variable,
                     b.metric_id AS canonical_var,
                     count(DISTINCT b.distribution_id) AS exact_binding_count,
                     max(b.confidence) AS maximum_binding_confidence,
                     max(x.quality_score) AS maximum_distribution_quality
              FROM ds_metric_bindings b
              JOIN ds_distributions x ON x.id = b.distribution_id
              GROUP BY b.dataset_id, b.request_dataset_id, b.metric_id
            )
            SELECT o.dataset_id, o.source, o.agency, o.title, o.description,
                   o.access_license, o.raw_variable, o.canonical_var,
                   o.row_count, o.distinct_year_count, o.minimum_year,
                   o.maximum_year, o.duplicate_year_count,
                   o.source_watermark_count, o.dataset_version_count,
                   o.acquisition_method_count,
                   o.nonpositive_value_count,
                   a.method, a.confidence, a.is_proxy, a.proxy_penalty,
                   coalesce(b.exact_binding_count, 0),
                   b.canonical_var,
                   b.maximum_binding_confidence,
                   b.maximum_distribution_quality
            FROM observation_groups o
            LEFT JOIN ds_variable_alignments a
              ON a.dataset_id = o.dataset_id
             AND a.raw_variable = o.raw_variable
             AND a.canonical_var = o.canonical_var
            LEFT JOIN exact_bindings b
              ON b.dataset_id = o.dataset_id
             AND b.raw_variable = o.raw_variable
             AND b.canonical_var = o.canonical_var
            ORDER BY o.dataset_id, o.raw_variable, o.canonical_var
            """,
            [country_code],
        ).fetchall()
        fields = (
            "dataset_id",
            "source",
            "agency",
            "title",
            "description",
            "access_license",
            "raw_variable",
            "canonical_variable",
            "row_count",
            "distinct_year_count",
            "minimum_year",
            "maximum_year",
            "duplicate_year_count",
            "source_watermark_count",
            "dataset_version_count",
            "acquisition_method_count",
            "nonpositive_value_count",
            "alignment_method",
            "alignment_confidence",
            "alignment_is_proxy",
            "alignment_proxy_penalty",
            "exact_binding_count",
            "metric_id",
            "maximum_binding_confidence",
            "maximum_distribution_quality",
        )
        all_rows = tuple(dict(zip(fields, row, strict=True)) for row in rows)
        index_rows = tuple(
            row
            for row in all_rows
            if data_forge_read_api.catalog.derive_catalog_unit_from_text(
                f"{row['title']} {row['description']}"
            )
            == expected_unit
        )
        points: dict[tuple[str, str, str], tuple[dict[str, object], ...]] = {}
        for row in index_rows:
            key = (
                str(row["dataset_id"]),
                str(row["raw_variable"]),
                str(row["canonical_variable"]),
            )
            point_rows = con.execute(
                """
                SELECT observation_id, year, value, source_watermark,
                       dataset_version, acquisition_method
                FROM ds_observations
                WHERE dataset_id = ? AND raw_variable = ? AND canonical_var = ?
                  AND country_code = ? AND value IS NOT NULL AND year IS NOT NULL
                ORDER BY year, observation_id
                """,
                [*key, country_code],
            ).fetchall()
            point_fields = (
                "observation_id",
                "year",
                "value",
                "source_watermark",
                "dataset_version",
                "acquisition_method",
            )
            points[key] = tuple(dict(zip(point_fields, point, strict=True)) for point in point_rows)
            row["series_key"] = key
    return index_rows, points, len(all_rows)


def _read_deflator_denominator(
    catalog_path: Path,
    *,
    metric_id: str,
) -> tuple[dict[str, object], ...]:
    with duckdb.connect(str(catalog_path), read_only=True) as con:
        rows = con.execute(
            """
            SELECT b.metric_id, b.dataset_id, b.distribution_id, b.connector_id,
                   b.profile_id, b.request_dataset_id, b.confidence,
                   b.execution_tier, d.source, d.agency, d.title,
                   coalesce(d.description, ''),
                   coalesce(nullif(d.access_license, ''), d.license, ''),
                   d.access_auth_required, x.parser_supported, x.quality_score,
                   coalesce(x.source_locator, x.url, ''),
                   d.temporal_start, d.temporal_end, d.themes
            FROM ds_metric_bindings b
            JOIN ds_datasets d ON d.id = b.dataset_id
            JOIN ds_distributions x
              ON x.id = b.distribution_id AND x.dataset_id = b.dataset_id
            WHERE b.metric_id = ?
            ORDER BY b.dataset_id, b.distribution_id, b.request_dataset_id
            """,
            [metric_id],
        ).fetchall()
    fields = (
        "metric_id",
        "dataset_id",
        "distribution_id",
        "connector_id",
        "profile_id",
        "request_dataset_id",
        "binding_confidence",
        "execution_tier",
        "source",
        "agency",
        "title",
        "description",
        "access_license",
        "access_auth_required",
        "parser_supported",
        "distribution_quality_score",
        "source_locator",
        "temporal_start",
        "temporal_end",
        "themes",
    )
    return tuple(dict(zip(fields, row, strict=True)) for row in rows)


def _build_local_disposition(
    row: Mapping[str, object],
    *,
    points: Sequence[Mapping[str, object]],
    role_policy: CatalogSelectionRoleConfig,
) -> LocalNominalDisposition:
    values = {
        **{key: value for key, value in row.items() if key != "series_key"},
        "role_policy": role_policy,
    }
    unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(
        f"{values['title']} {values['description']}"
    )
    provisional = LocalNominalDisposition.model_construct(
        **values,
        derived_unit=unit,
        acceptance_alignment_score=0.0,
        rejection_codes=(),
        eligible=False,
        observation_projection_sha256=_point_projection_sha256(points),
        projection_sha256="sha256:" + "0" * 64,
    )
    evaluation = _evaluate_local_candidate(provisional)
    rejections = _local_rejection_codes(provisional)
    payload = {
        **values,
        "derived_unit": unit,
        "acceptance_alignment_score": evaluation.semantic_alignment_score,
        "rejection_codes": rejections,
        "eligible": not rejections,
        "observation_projection_sha256": _point_projection_sha256(points),
    }
    return LocalNominalDisposition(
        **payload,
        projection_sha256=content_sha256(_json_values(payload)),
    )


def _build_deflator_disposition(
    row: Mapping[str, object],
    *,
    live_families: tuple[str, ...],
    role_policy: CatalogSelectionRoleConfig,
) -> DeflatorCarrierDisposition:
    themes = tuple(sorted(set(_string_values(row.get("themes")))))
    title = str(row["title"])
    description = str(row["description"])
    unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(f"{title} {description}")
    base_year = _reference_base_year(
        f"{title} {description}",
        pattern=role_policy.reference_value_pattern,
    )
    values: dict[str, object] = {
        **row,
        "role_policy": role_policy,
        "themes": themes,
        "derived_unit": unit,
        "reference_base_year": base_year,
        "live_family": str(row["connector_id"]) in live_families,
        "acceptance_alignment_score": 0.0,
    }
    provisional = DeflatorCarrierDisposition.model_construct(
        **values,
        rejection_codes=(),
        eligible=False,
        projection_sha256="sha256:" + "0" * 64,
    )
    evaluation = _evaluate_live_candidate(provisional)
    rejections = _deflator_rejection_codes(provisional)
    payload = {
        **values,
        "acceptance_alignment_score": evaluation.semantic_alignment_score,
        "rejection_codes": rejections,
        "eligible": not rejections,
    }
    return DeflatorCarrierDisposition(
        **payload,
        projection_sha256=content_sha256(_json_values(payload)),
    )


def _build_local_deflator_disposition(
    row: Mapping[str, object],
    *,
    points: Sequence[Mapping[str, object]],
    nominal_years: Sequence[int],
    role_policy: CatalogSelectionRoleConfig,
) -> LocalDeflatorDisposition:
    values = {
        **{key: value for key, value in row.items() if key != "series_key"},
        "role_policy": role_policy,
    }
    title = str(values["title"])
    description = str(values["description"])
    unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(f"{title} {description}")
    base_year = _reference_base_year(
        f"{title} {description}",
        pattern=role_policy.reference_value_pattern,
    )
    point_years = {int(point["year"]) for point in points}
    expected_years = {int(year) for year in nominal_years}
    overlap = tuple(sorted(point_years & expected_years))
    missing = tuple(sorted(expected_years - point_years))
    projection_sha = _point_projection_sha256(points)
    provisional = LocalDeflatorDisposition.model_construct(
        **values,
        derived_unit=unit,
        reference_base_year=base_year,
        overlapping_nominal_years=overlap,
        missing_nominal_years=missing,
        rejection_codes=(),
        eligible=False,
        observation_projection_sha256=projection_sha,
        projection_sha256="sha256:" + "0" * 64,
    )
    rejections = _local_deflator_rejection_codes(provisional)
    payload = {
        **values,
        "derived_unit": unit,
        "reference_base_year": base_year,
        "overlapping_nominal_years": overlap,
        "missing_nominal_years": missing,
        "rejection_codes": rejections,
        "eligible": not rejections,
        "observation_projection_sha256": projection_sha,
    }
    return LocalDeflatorDisposition(
        **payload,
        projection_sha256=content_sha256(_json_values(payload)),
    )


def _local_rejection_codes(row: LocalNominalDisposition) -> tuple[str, ...]:
    return tuple(code.value for code in _evaluate_local_candidate(row).rejection_codes)


def _deflator_rejection_codes(row: DeflatorCarrierDisposition) -> tuple[str, ...]:
    codes = {code.value for code in _evaluate_live_candidate(row).rejection_codes}
    if not row.live_family:
        codes.add("family_not_live_characterized")
    return tuple(sorted(codes))


def _local_deflator_rejection_codes(row: LocalDeflatorDisposition) -> tuple[str, ...]:
    codes = {code.value for code in _evaluate_local_candidate(row).rejection_codes}
    if row.nonpositive_value_count:
        codes.add("nonpositive_index_value")
    if row.missing_nominal_years:
        codes.add("exact_year_overlap_missing")
    return tuple(sorted(codes))


def _evaluate_local_candidate(
    row: LocalNominalDisposition | LocalDeflatorDisposition,
) -> data_forge_read_api.catalog.CatalogSelectionCandidateEvaluation:
    return data_forge_read_api.catalog.evaluate_catalog_selection_candidate(
        row.role_policy,
        CatalogSelectionCandidateEvidence(
            candidate_kind="local_series",
            catalog_unit=row.derived_unit,
            metric_id=row.metric_id,
            canonical_variable=row.canonical_variable,
            title=row.title,
            description=row.description,
            access_license=row.access_license,
            alignment_method=row.alignment_method,
            alignment_confidence=row.alignment_confidence,
            alignment_is_proxy=row.alignment_is_proxy,
            alignment_proxy_penalty=row.alignment_proxy_penalty,
            exact_binding_count=row.exact_binding_count,
            maximum_binding_confidence=row.maximum_binding_confidence,
            maximum_distribution_quality=row.maximum_distribution_quality,
            point_count=row.row_count,
            distinct_year_count=row.distinct_year_count,
            duplicate_year_count=row.duplicate_year_count,
            source_watermark_count=row.source_watermark_count,
            dataset_version_count=row.dataset_version_count,
            acquisition_method_count=row.acquisition_method_count,
        ),
    )


def _evaluate_live_candidate(
    row: DeflatorCarrierDisposition,
) -> data_forge_read_api.catalog.CatalogSelectionCandidateEvaluation:
    return data_forge_read_api.catalog.evaluate_catalog_selection_candidate(
        row.role_policy,
        CatalogSelectionCandidateEvidence(
            candidate_kind="live_carrier",
            catalog_unit=row.derived_unit,
            metric_id=row.metric_id,
            canonical_variable=row.metric_id,
            title=row.title,
            description=row.description,
            access_license=row.access_license,
            alignment_method="exact_catalog_binding",
            alignment_confidence=row.binding_confidence,
            alignment_is_proxy=False,
            alignment_proxy_penalty=0.0,
            exact_binding_count=1,
            maximum_binding_confidence=row.binding_confidence,
            maximum_distribution_quality=row.distribution_quality_score,
            connector_id=row.connector_id,
            execution_tier=row.execution_tier,
            access_auth_required=row.access_auth_required,
            parser_supported=row.parser_supported,
            themes=row.themes,
        ),
    )


def _local_rank_key(row: LocalNominalDisposition) -> tuple[object, ...]:
    return (
        -row.acceptance_alignment_score,
        -row.distinct_year_count,
        -(row.alignment_confidence or 0.0),
        -(row.maximum_binding_confidence or 0.0),
        -(row.maximum_distribution_quality or 0.0),
        row.dataset_id,
        row.raw_variable,
        row.canonical_variable,
    )


def _deflator_rank_key(row: DeflatorCarrierDisposition) -> tuple[object, ...]:
    return (
        -row.acceptance_alignment_score,
        -row.binding_confidence,
        -row.distribution_quality_score,
        row.dataset_id,
        row.distribution_id,
        row.request_dataset_id,
    )


def _local_deflator_rank_key(row: LocalDeflatorDisposition) -> tuple[object, ...]:
    return (
        -(row.alignment_confidence or 0.0),
        -(row.maximum_binding_confidence or 0.0),
        -(row.maximum_distribution_quality or 0.0),
        -row.distinct_year_count,
        row.dataset_id,
        row.raw_variable,
        row.canonical_variable,
    )


def _execution_selection(
    row: DeflatorCarrierDisposition,
    *,
    live_families: tuple[str, ...],
    catalog_denominator_count: int,
    eligible_count: int,
    decisive_rejections: dict[str, int],
) -> LiveTargetSelection:
    target_variable = row.role_policy.owner_canonical_variable
    score = data_forge_read_api.catalog.score_variable_pair(
        left_name=target_variable,
        right_name=row.metric_id,
        left_unit=row.role_policy.catalog_unit,
        right_unit=row.role_policy.catalog_unit,
    )
    values: dict[str, object] = {
        "target_variable": target_variable,
        "canonical_unit": row.role_policy.catalog_unit,
        "backlog_rank": 1,
        "demand_sources": ("GY-N13b.item7.real_terms_acceptance",),
        "live_family_denominator": live_families,
        "eligible_target_denominator": (target_variable,),
        "catalog_candidate_denominator": catalog_denominator_count,
        "eligible_catalog_candidate_count": eligible_count,
        "rejected_candidate_counts": decisive_rejections,
        "source_catalog_dataset_id": row.dataset_id,
        "source_catalog_distribution_id": row.distribution_id,
        "connector_id": row.connector_id,
        "profile_id": row.profile_id,
        "request_dataset_id": row.request_dataset_id,
        "upstream_metric_id": row.metric_id,
        "source": row.source,
        "agency": row.agency,
        "source_locator": row.source_locator,
        "title": row.title,
        "description": row.description,
        "access_license": row.access_license,
        "execution_tier": row.execution_tier,
        "binding_confidence": row.binding_confidence,
        "distribution_quality_score": row.distribution_quality_score,
        "temporal_start": row.temporal_start,
        "temporal_end": row.temporal_end,
        "alignment_score": score,
    }
    provisional = LiveTargetSelection.model_construct(
        **values,
        selection_content_sha256="sha256:" + "0" * 64,
    )
    return LiveTargetSelection(
        **values,
        selection_content_sha256=content_sha256(provisional.identity_payload()),
    )


def _live_families(census: Mapping[str, object]) -> tuple[tuple[str, ...], dict[str, object]]:
    raw = census.get("family_scorecards")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise AcceptanceSelectionError("acceptance_family_scorecards_missing")
    projection_rows: list[dict[str, object]] = []
    live: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            raise AcceptanceSelectionError("acceptance_family_scorecard_invalid")
        connector_id = str(item.get("connector_id") or "").strip()
        state = str(item.get("family_liveness_state") or "").strip()
        if not connector_id:
            raise AcceptanceSelectionError("acceptance_connector_id_missing")
        projection_rows.append(
            {
                "connector_id": connector_id,
                "family_liveness_state": state,
                "dry_run_passed": bool(item.get("dry_run_passed")),
                "liveness_counts": item.get("liveness_counts"),
            }
        )
        if state.startswith("live") and bool(item.get("dry_run_passed")):
            live.add(connector_id)
    if not live:
        raise AcceptanceSelectionError("acceptance_live_family_denominator_empty")
    projection_rows.sort(key=lambda row: str(row["connector_id"]))
    return tuple(sorted(live)), {"family_scorecards": projection_rows}


def _reference_base_year(value: str, *, pattern: str | None) -> int | None:
    if pattern is None:
        return None
    match = re.search(pattern, value, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _rejection_counts(rows: Sequence[Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update(row.rejection_codes)
    return dict(sorted(counts.items()))


def _decisive_rejection_counts(rows: Sequence[Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        if row.eligible:
            continue
        counts[row.rejection_codes[0]] += 1
    return dict(sorted(counts.items()))


def _point_projection_sha256(points: Sequence[Mapping[str, object] | LocalNominalPoint]) -> str:
    payload: list[dict[str, object]] = []
    for point in points:
        values = (
            point.model_dump(mode="json") if isinstance(point, LocalNominalPoint) else dict(point)
        )
        values["value"] = str(Decimal(str(values["value"])))
        payload.append(_json_values(values))
    return content_sha256(payload)


def _journal_transport_call_count(path: Path, *, attempt_id: str) -> int:
    try:
        lines = Path(path).read_bytes().splitlines(keepends=True)
    except OSError as exc:
        raise AcceptanceSelectionError("acceptance_journal_unreadable") from exc
    count = 0
    for line in lines:
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcceptanceSelectionError("acceptance_journal_not_canonical") from exc
        if not isinstance(event, Mapping) or canonical_json_bytes(event) != line:
            raise AcceptanceSelectionError("acceptance_journal_not_canonical")
        if event.get("attempt_id") == attempt_id and event.get("event_kind") == "transport_attempt":
            count += 1
    return count


def _string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(str(item) for item in value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return (value,)
        if isinstance(decoded, Sequence) and not isinstance(decoded, (str, bytes, bytearray)):
            return tuple(str(item) for item in decoded)
        return (str(decoded),)
    return ()


def _json_values(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_values(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_values(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


def _stable_repo_ref(path: Path) -> str:
    resolved = Path(path).resolve()
    parts = resolved.parts
    indexes = tuple(index for index, part in enumerate(parts) if part == "policy-engine")
    if indexes:
        candidate = Path(*parts[indexes[-1] + 1 :])
        return f"repo://{candidate.as_posix()}"
    return resolved.as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


__all__ = [
    "DEFAULT_ACCEPTANCE_AUTHORITY_OWNER",
    "DEFAULT_ACCEPTANCE_CASE",
    "DEFAULT_ACCEPTANCE_DEFLATOR_HARNESS",
    "DEFAULT_ACCEPTANCE_FALLBACK_SELECTION",
    "DEFAULT_ACCEPTANCE_INPUT_SELECTION",
    "DEFAULT_ACCEPTANCE_LIVE_EXECUTION",
    "DEFAULT_DERIVATION_FAMILY_REGISTRY",
    "AcceptanceAuthorityOwner",
    "AcceptanceAuthorityOwners",
    "AcceptanceCaseReceipt",
    "AcceptanceDerivationOwner",
    "AcceptanceFallbackSelection",
    "AcceptanceInputSelection",
    "AcceptanceLiveExecutionReceipt",
    "AcceptanceSelectionError",
    "CatalogSelectionPolicyConfig",
    "CatalogSelectionRoleConfig",
    "DeflatorCarrierDisposition",
    "LocalDeflatorDisposition",
    "LocalDeflatorPoint",
    "LocalNominalDisposition",
    "LocalNominalPoint",
    "derive_acceptance_authority_owners",
    "derive_acceptance_fallback_selection",
    "derive_acceptance_input_selection",
    "derive_acceptance_live_execution_receipt",
    "materialize_acceptance_case",
    "verify_persisted_acceptance_case",
]
