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

from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.fabric.data_plane import (
    LiveAttemptTerminal,
    canonical_json_bytes,
    content_sha256,
    resolve_live_attempt_terminals,
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

_EXECUTABLE_TIERS = frozenset({"fetchable", "transport_ready"})
_MONETARY_UNITS = frozenset({"usd", "uah"})
_LOCAL_ALIGNMENT_THRESHOLD = 0.8
_NOMINAL_ANCHOR = "gross domestic product nominal current usd"
_DEFLATOR_ANCHOR = "consumer price index reference base"
_BASE_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\s*=\s*100\b", re.IGNORECASE)


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
    "DEFAULT_ACCEPTANCE_DEFLATOR_HARNESS",
    "DEFAULT_ACCEPTANCE_INPUT_SELECTION",
    "DEFAULT_ACCEPTANCE_LIVE_EXECUTION",
    "AcceptanceAuthorityOwner",
    "AcceptanceAuthorityOwners",
    "AcceptanceInputSelection",
    "AcceptanceLiveExecutionReceipt",
    "AcceptanceSelectionError",
    "DeflatorCarrierDisposition",
    "LocalNominalDisposition",
    "LocalNominalPoint",
    "derive_acceptance_authority_owners",
    "derive_acceptance_input_selection",
    "derive_acceptance_live_execution_receipt",
]
