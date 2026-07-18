"""Recomputing owners for the GY-N13b real-terms acceptance inputs.

The selector is deliberately read-only.  It enumerates every local Ukraine
series group before reducing to monetary candidates, and every catalog binding
for the inflation metric before selecting one connector-executable price index.
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
from typing import Any, Literal, Self

import duckdb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts
from polisyos.data_forge import read_api as data_forge_read_api
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
from polisyos.ir.kernel import DimensionlessUnit, MoneyUnit
from polisyos.runtime.quality.acquisition_executor import (
    ObservationProvenanceClass,
    derive_observation_provenance_rejections,
)
from polisyos.runtime.quality.derived_observations import (
    DERIVATION_CERTIFICATE_KIND,
    AuthorityProjection,
    CertifiedDerivationConsumption,
    DerivationCertificate,
    DerivationRecipe,
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

_EXECUTABLE_TIERS = frozenset({"fetchable", "transport_ready"})
_MONETARY_UNITS = frozenset({"usd", "uah"})
_LOCAL_ALIGNMENT_THRESHOLD = 0.8
_NOMINAL_ANCHOR = "gross domestic product nominal current usd"
_DEFLATOR_ANCHOR = "consumer price index reference base"
_BASE_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\s*=\s*100\b", re.IGNORECASE)
_ACCEPTANCE_PRODUCER = artifacts.ProducerInfo(
    component="tools.quality.validation.layer3_gy_n13b_acceptance",
    version="1.0.0",
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
    canonical_variable: str = Field(min_length=1)
    derived_unit: str | None
    row_count: int = Field(ge=1)
    distinct_year_count: int = Field(ge=1)
    minimum_year: int = Field(ge=1900, le=2200)
    maximum_year: int = Field(ge=1900, le=2200)
    duplicate_year_count: int = Field(ge=0)
    source_watermark_count: int = Field(ge=0)
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
        score = data_forge_read_api.catalog.score_variable_pair(
            left_name=_NOMINAL_ANCHOR,
            right_name=(f"{self.canonical_variable} {self.raw_variable} {self.title}"),
            left_unit="usd",
            right_unit=self.derived_unit or "unresolved",
        )
        if abs(self.acceptance_alignment_score - score.overall_score) > 1e-9:
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
    """One inflation binding classified for the exact CPI-deflator role."""

    metric_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    distribution_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
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
        expected_year = _reference_base_year(f"{self.title} {self.description}")
        if self.reference_base_year != expected_year:
            raise ValueError("deflator base year must be parsed from catalog evidence")
        expected_rejections = _deflator_rejection_codes(self)
        if self.rejection_codes != expected_rejections:
            raise ValueError("deflator rejection codes must be recomputed")
        if self.eligible != (not expected_rejections):
            raise ValueError("deflator eligibility must derive from rejection codes")
        score = data_forge_read_api.catalog.score_variable_pair(
            left_name=_DEFLATOR_ANCHOR,
            right_name=f"{self.request_dataset_id} {self.title}",
            left_unit="index",
            right_unit=self.derived_unit or "unresolved",
        )
        if abs(self.acceptance_alignment_score - score.overall_score) > 1e-9:
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
    country_code: Literal["UA"]
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
    """Projection binding the selected CPI carrier to the canonical authority graph."""

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
    """Reopened journal/CAS result for the single authorized CPI data call."""

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
    canonical_variable: str = Field(min_length=1)
    row_count: int = Field(ge=1)
    distinct_year_count: int = Field(ge=1)
    minimum_year: int = Field(ge=1900, le=2200)
    maximum_year: int = Field(ge=1900, le=2200)
    duplicate_year_count: int = Field(ge=0)
    source_watermark_count: int = Field(ge=0)
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
        expected_year = _reference_base_year(f"{self.title} {self.description}")
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
    recipe_base_year_selection: Literal["median_exact_overlap_year"] | None
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
            self.recipe_base_year,
            self.deflator_version,
        )
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
            median = self.exact_overlap_years[len(self.exact_overlap_years) // 2]
            if self.recipe_base_year != median:
                raise ValueError("recipe base year must be the median exact overlap year")
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
    basis_mismatch_detail_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    model_output_observation_rejection_codes: tuple[str, ...]
    disposition: Literal["accepted_local_fallback"]
    receipt_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _receipt_is_recomputed(self) -> Self:
        if str(self.recipe.nominal_input.artifact_id) != self.nominal_series_artifact_id:
            raise ValueError("acceptance recipe nominal input drift")
        if str(self.recipe.deflator_input.artifact_id) != self.deflator_series_artifact_id:
            raise ValueError("acceptance recipe deflator input drift")
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


def derive_acceptance_input_selection(
    *,
    catalog_path: Path,
    census_path: Path,
    r1_paid_success_elapsed_seconds: float,
) -> AcceptanceInputSelection:
    """Recompute the complete local nominal and live deflator denominators."""

    catalog = Path(catalog_path)
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
    local_rows, local_points, all_local_groups = _read_local_denominator(catalog)
    deflator_rows = _read_deflator_denominator(catalog)

    local_dispositions = tuple(
        _build_local_disposition(row, points=local_points[row["series_key"]]) for row in local_rows
    )
    deflator_dispositions = tuple(
        _build_deflator_disposition(row, live_families=live_families) for row in deflator_rows
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
    if selected_nominal is not None and selected_deflator is not None:
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
        "country_code": "UA",
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
        "disposition": (
            "admissible_pair"
            if selected_nominal is not None and selected_deflator is not None
            else "acceptance_inputs_inadmissible"
        ),
        "selected_nominal": selected_nominal,
        "selected_nominal_points": selected_points,
        "selected_deflator": selected_deflator,
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
    """Extend the canonical registry/provision with one exact CPI live carrier."""

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
) -> AcceptanceFallbackSelection:
    """Recompute every local index series after the one authorized live terminal."""

    selected = AcceptanceInputSelection.model_validate(input_selection.model_dump(mode="python"))
    live = AcceptanceLiveExecutionReceipt.model_validate(live_execution.model_dump(mode="python"))
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

    nominal_years = tuple(point.year for point in selected.selected_nominal_points)
    rows, points, all_local_groups = _read_local_index_denominator(catalog)
    dispositions = tuple(
        _build_local_deflator_disposition(
            row,
            points=points[row["series_key"]],
            nominal_years=nominal_years,
        )
        for row in rows
    )
    eligible = tuple(row for row in dispositions if row.eligible)
    selected_deflator = min(eligible, key=_local_deflator_rank_key) if eligible else None
    selected_points: tuple[LocalDeflatorPoint, ...] = ()
    exact_overlap_years: tuple[int, ...] = ()
    base_year_selection: Literal["median_exact_overlap_year"] | None = None
    base_year: int | None = None
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
        base_year_selection = "median_exact_overlap_year"
        base_year = exact_overlap_years[len(exact_overlap_years) // 2]
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
        "recipe_base_year_selection": base_year_selection,
        "recipe_base_year": base_year,
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
) -> AcceptanceCaseReceipt:
    """Materialize and consume the certified local-fallback derivation once."""

    selected = AcceptanceInputSelection.model_validate(input_selection.model_dump(mode="python"))
    fallback = AcceptanceFallbackSelection.model_validate(
        fallback_selection.model_dump(mode="python")
    )
    if (
        fallback.input_selection_sha256 != selected.selection_sha256
        or fallback.disposition != "local_fallback_admissible"
        or selected.selected_nominal is None
        or fallback.selected_deflator is None
        or fallback.recipe_base_year is None
        or fallback.deflator_version is None
    ):
        raise AcceptanceSelectionError("acceptance_case_inputs_inadmissible")

    nominal_authority = _persist_input_authority(
        store,
        role="nominal_monetary_series",
        baseline_sha256=fallback.baseline_sha256,
        disposition_payload=selected.selected_nominal.identity_payload(),
        observation_projection_sha256=(selected.selected_nominal.observation_projection_sha256),
        alignment_confidence=selected.selected_nominal.alignment_confidence,
        binding_confidence=selected.selected_nominal.maximum_binding_confidence,
        distribution_quality=selected.selected_nominal.maximum_distribution_quality,
    )
    deflator_authority = _persist_input_authority(
        store,
        role="price_index_series",
        baseline_sha256=fallback.baseline_sha256,
        disposition_payload=fallback.selected_deflator.identity_payload(),
        observation_projection_sha256=(fallback.selected_deflator.observation_projection_sha256),
        alignment_confidence=fallback.selected_deflator.alignment_confidence,
        binding_confidence=fallback.selected_deflator.maximum_binding_confidence,
        distribution_quality=fallback.selected_deflator.maximum_distribution_quality,
    )
    nominal_basis = EconomicBasis(
        unit=MoneyUnit(
            kind="money",
            currency="USD",
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
    deflator_basis = PriceIndexBasis(
        unit=DimensionlessUnit(kind="dimensionless", label="index"),
        index_id="consumer_price_index",
        index_version=fallback.deflator_version,
        reference_base_year=fallback.selected_deflator.reference_base_year,
        seasonal_adjustment="not_seasonally_adjusted",
    )
    nominal_series = EconomicSeries(
        variable_id=(f"{selected.selected_nominal.canonical_variable}_nominal_usd"),
        basis=nominal_basis,
        points=tuple(
            SeriesPoint(year=point.year, value=point.value)
            for point in selected.selected_nominal_points
        ),
        authority=nominal_authority,
        observation_class="observed",
    )
    deflator_series = PriceIndexSeries(
        variable_id="consumer_price_index",
        basis=deflator_basis,
        points=tuple(
            SeriesPoint(year=point.year, value=point.value)
            for point in fallback.selected_deflator_points
        ),
        authority=deflator_authority,
        observation_class="observed",
    )
    nominal_ref = persist_economic_series(
        store,
        nominal_series,
        producer=_ACCEPTANCE_PRODUCER,
    )
    deflator_ref = persist_price_index_series(
        store,
        deflator_series,
        producer=_ACCEPTANCE_PRODUCER,
    )
    output_basis = _acceptance_output_basis(
        deflator_ref=deflator_ref,
        deflator_version=fallback.deflator_version,
        base_year=fallback.recipe_base_year,
        currency="USD",
    )
    assumptions = (
        f"base_year={fallback.recipe_base_year}",
        "deflator_choice=consumer_price_index",
        f"deflator_reference_base_year={fallback.selected_deflator.reference_base_year}",
        f"deflator_version={fallback.deflator_version}",
        "exact-year joins; no interpolation",
        "real_t = nominal_t * CPI_base / CPI_t",
        "recipe_base_year_selection=median_exact_overlap_year",
    )
    recipe = build_cpi_derivation_recipe(
        store,
        nominal_ref=nominal_ref,
        deflator_ref=deflator_ref,
        output_variable_id=(
            f"{selected.selected_nominal.canonical_variable}_real_usd_{fallback.recipe_base_year}"
        ),
        output_basis=output_basis,
        assumptions=assumptions,
    )
    first = materialize_cpi_real_terms(store, recipe)
    if require_first_cache_miss and first.cache_hit:
        raise AcceptanceSelectionError("acceptance_first_materialization_not_cache_miss")
    second = materialize_cpi_real_terms(store, recipe)
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
        build_cpi_derivation_recipe(
            store,
            nominal_ref=nominal_ref,
            deflator_ref=deflator_ref,
            output_variable_id=(
                f"{selected.selected_nominal.canonical_variable}_real_uah_"
                f"{fallback.recipe_base_year}"
            ),
            output_basis=_acceptance_output_basis(
                deflator_ref=deflator_ref,
                deflator_version=fallback.deflator_version,
                base_year=fallback.recipe_base_year,
                currency="UAH",
            ),
            assumptions=assumptions,
        )
    except DerivationRefusalError as exc:
        if exc.code is not DerivationRefusalCode.BASIS_MISMATCH:
            raise
        basis_mismatch_detail_sha256 = content_sha256(
            {"code": exc.code.value, "detail": exc.detail}
        )
    else:
        raise AcceptanceSelectionError("acceptance_basis_mismatch_did_not_refuse")

    values: dict[str, object] = {
        "schema_version": "policyos.layer3.gy.n13b.derived_acceptance.v1",
        "fallback_selection_sha256": fallback.selection_sha256,
        "baseline_sha256": fallback.baseline_sha256,
        "source_epoch": 0,
        "nominal_series_artifact_id": str(nominal_ref.artifact_id),
        "deflator_series_artifact_id": str(deflator_ref.artifact_id),
        "recipe": recipe,
        "certificate": second.certificate,
        "derived_artifact_id": str(second.derived_artifact_ref.artifact_id),
        "certificate_artifact_id": str(second.certificate_artifact_ref.artifact_id),
        "first_materialization_cache_hit": False,
        "second_materialization_cache_hit": True,
        "consumers": consumer_executions,
        "basis_mismatch_refusal_code": DerivationRefusalCode.BASIS_MISMATCH.value,
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


def _acceptance_output_basis(
    *,
    deflator_ref: artifacts.ArtifactRef,
    deflator_version: str,
    base_year: int,
    currency: str,
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
        deflator_version=deflator_version,
        per_capita=False,
        seasonal_adjustment="not_seasonally_adjusted",
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
                     count(o.acquisition_method) AS acquisition_method_count
              FROM ds_observations o
              JOIN ds_datasets d ON d.id = o.dataset_id
              WHERE o.country_code = 'UA'
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
                   o.source_watermark_count, o.acquisition_method_count,
                   a.method, a.confidence, a.is_proxy, a.proxy_penalty,
                   coalesce(b.exact_binding_count, 0),
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
            """
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
            "acquisition_method_count",
            "alignment_method",
            "alignment_confidence",
            "alignment_is_proxy",
            "alignment_proxy_penalty",
            "exact_binding_count",
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
            in _MONETARY_UNITS
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
                  AND country_code = 'UA' AND value IS NOT NULL AND year IS NOT NULL
                ORDER BY year, observation_id
                """,
                list(key),
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
                     count(o.acquisition_method) AS acquisition_method_count,
                     sum(CASE WHEN o.value <= 0 THEN 1 ELSE 0 END) AS nonpositive_value_count
              FROM ds_observations o
              JOIN ds_datasets d ON d.id = o.dataset_id
              WHERE o.country_code = 'UA'
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
                   o.source_watermark_count, o.acquisition_method_count,
                   o.nonpositive_value_count,
                   a.method, a.confidence, a.is_proxy, a.proxy_penalty,
                   coalesce(b.exact_binding_count, 0),
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
            """
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
            "acquisition_method_count",
            "nonpositive_value_count",
            "alignment_method",
            "alignment_confidence",
            "alignment_is_proxy",
            "alignment_proxy_penalty",
            "exact_binding_count",
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
            == "index"
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
                  AND country_code = 'UA' AND value IS NOT NULL AND year IS NOT NULL
                ORDER BY year, observation_id
                """,
                list(key),
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


def _read_deflator_denominator(catalog_path: Path) -> tuple[dict[str, object], ...]:
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
            WHERE b.metric_id = 'inflation'
            ORDER BY b.dataset_id, b.distribution_id, b.request_dataset_id
            """
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
) -> LocalNominalDisposition:
    values = {key: value for key, value in row.items() if key != "series_key"}
    unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(
        f"{values['title']} {values['description']}"
    )
    score = data_forge_read_api.catalog.score_variable_pair(
        left_name=_NOMINAL_ANCHOR,
        right_name=(f"{values['canonical_variable']} {values['raw_variable']} {values['title']}"),
        left_unit="usd",
        right_unit=unit or "unresolved",
    )
    provisional = LocalNominalDisposition.model_construct(
        **values,
        derived_unit=unit,
        acceptance_alignment_score=score.overall_score,
        rejection_codes=(),
        eligible=False,
        observation_projection_sha256=_point_projection_sha256(points),
        projection_sha256="sha256:" + "0" * 64,
    )
    rejections = _local_rejection_codes(provisional)
    payload = {
        **values,
        "derived_unit": unit,
        "acceptance_alignment_score": score.overall_score,
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
) -> DeflatorCarrierDisposition:
    themes = tuple(sorted(set(_string_values(row.get("themes")))))
    title = str(row["title"])
    description = str(row["description"])
    unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(f"{title} {description}")
    base_year = _reference_base_year(f"{title} {description}")
    score = data_forge_read_api.catalog.score_variable_pair(
        left_name=_DEFLATOR_ANCHOR,
        right_name=f"{row['request_dataset_id']} {title}",
        left_unit="index",
        right_unit=unit or "unresolved",
    )
    values: dict[str, object] = {
        **row,
        "themes": themes,
        "derived_unit": unit,
        "reference_base_year": base_year,
        "live_family": str(row["connector_id"]) in live_families,
        "acceptance_alignment_score": score.overall_score,
    }
    provisional = DeflatorCarrierDisposition.model_construct(
        **values,
        rejection_codes=(),
        eligible=False,
        projection_sha256="sha256:" + "0" * 64,
    )
    rejections = _deflator_rejection_codes(provisional)
    payload = {**values, "rejection_codes": rejections, "eligible": not rejections}
    return DeflatorCarrierDisposition(
        **payload,
        projection_sha256=content_sha256(_json_values(payload)),
    )


def _build_local_deflator_disposition(
    row: Mapping[str, object],
    *,
    points: Sequence[Mapping[str, object]],
    nominal_years: Sequence[int],
) -> LocalDeflatorDisposition:
    values = {key: value for key, value in row.items() if key != "series_key"}
    title = str(values["title"])
    description = str(values["description"])
    unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(f"{title} {description}")
    base_year = _reference_base_year(f"{title} {description}")
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
    codes: set[str] = set()
    if row.derived_unit not in _MONETARY_UNITS:
        codes.add("monetary_unit_unresolved")
    if (
        data_forge_read_api.catalog.derive_license_disposition(row.access_license).value
        != "admissible_open"
    ):
        codes.add("license_not_admissible")
    if row.distinct_year_count < 2:
        codes.add("insufficient_exact_years")
    if row.duplicate_year_count:
        codes.add("duplicate_years")
    if row.source_watermark_count != row.row_count:
        codes.add("source_watermark_missing")
    if row.acquisition_method_count != row.row_count:
        codes.add("acquisition_method_missing")
    if row.alignment_method is None or row.alignment_confidence is None:
        codes.add("alignment_missing")
    elif row.alignment_confidence < _LOCAL_ALIGNMENT_THRESHOLD:
        codes.add("alignment_below_owner_threshold")
    if row.alignment_is_proxy is not False:
        codes.add("proxy_or_unresolved_alignment")
    if row.exact_binding_count < 1:
        codes.add("metric_binding_missing")
    title = row.title.casefold()
    if "current" not in title:
        codes.add("nominal_basis_not_declared")
    if "per capita" in title:
        codes.add("per_capita_basis_out_of_scope")
    if "seas. adj" in title or "seasonally adjusted" in title:
        codes.add("seasonal_basis_out_of_scope")
    return tuple(sorted(codes))


def _deflator_rejection_codes(row: DeflatorCarrierDisposition) -> tuple[str, ...]:
    codes: set[str] = set()
    if row.metric_id != "inflation":
        codes.add("metric_role_mismatch")
    if not row.live_family:
        codes.add("family_not_live_characterized")
    if row.connector_id != "worldbank.wdi":
        codes.add("executor_connector_unimplemented")
    if row.execution_tier not in _EXECUTABLE_TIERS:
        codes.add("execution_tier_not_executable")
    if (
        data_forge_read_api.catalog.derive_license_disposition(row.access_license).value
        != "admissible_open"
    ):
        codes.add("license_not_admissible")
    if row.access_auth_required:
        codes.add("auth_required")
    if not row.parser_supported:
        codes.add("parser_unsupported")
    if row.derived_unit != "index":
        codes.add("price_index_basis_missing")
    normalized = f"{row.title} {row.description}".casefold()
    if "consumer price index" not in normalized:
        codes.add("consumer_price_index_role_missing")
    if row.reference_base_year is None:
        codes.add("reference_base_year_missing")
    if "World Development Indicators" not in row.themes:
        codes.add("current_wdi_theme_missing")
    if any("archive" in theme.casefold() for theme in row.themes):
        codes.add("archived_carrier")
    return tuple(sorted(codes))


def _local_deflator_rejection_codes(row: LocalDeflatorDisposition) -> tuple[str, ...]:
    codes: set[str] = set()
    if row.derived_unit != "index":
        codes.add("price_index_basis_missing")
    if (
        data_forge_read_api.catalog.derive_license_disposition(row.access_license).value
        != "admissible_open"
    ):
        codes.add("license_not_admissible")
    if row.distinct_year_count < 2:
        codes.add("insufficient_exact_years")
    if row.duplicate_year_count:
        codes.add("duplicate_years")
    if row.source_watermark_count != row.row_count:
        codes.add("source_watermark_missing")
    if row.acquisition_method_count != row.row_count:
        codes.add("acquisition_method_missing")
    if row.nonpositive_value_count:
        codes.add("nonpositive_index_value")
    if row.alignment_method is None or row.alignment_confidence is None:
        codes.add("alignment_missing")
    elif row.alignment_confidence < _LOCAL_ALIGNMENT_THRESHOLD:
        codes.add("alignment_below_owner_threshold")
    if row.alignment_is_proxy is not False:
        codes.add("proxy_or_unresolved_alignment")
    if row.exact_binding_count < 1:
        codes.add("metric_binding_missing")
    if row.canonical_variable != "inflation":
        codes.add("deflator_metric_role_mismatch")
    normalized = f"{row.title} {row.description}".casefold()
    if "consumer price index" not in normalized:
        codes.add("consumer_price_index_role_missing")
    if "annual %" in normalized or "percentage change" in normalized:
        codes.add("rate_not_price_index_level")
    if row.reference_base_year is None:
        codes.add("reference_base_year_missing")
    if row.missing_nominal_years:
        codes.add("exact_year_overlap_missing")
    return tuple(sorted(codes))


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
    score = data_forge_read_api.catalog.score_variable_pair(
        left_name="inflation",
        right_name="inflation",
        left_unit="index",
        right_unit="index",
    )
    values: dict[str, object] = {
        "target_variable": "inflation",
        "canonical_unit": "index",
        "backlog_rank": 1,
        "demand_sources": ("GY-N13b.item7.real_terms_acceptance",),
        "live_family_denominator": live_families,
        "eligible_target_denominator": ("inflation",),
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


def _reference_base_year(value: str) -> int | None:
    match = _BASE_YEAR_RE.search(value)
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
    "AcceptanceAuthorityOwner",
    "AcceptanceAuthorityOwners",
    "AcceptanceCaseReceipt",
    "AcceptanceFallbackSelection",
    "AcceptanceInputSelection",
    "AcceptanceLiveExecutionReceipt",
    "AcceptanceSelectionError",
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
