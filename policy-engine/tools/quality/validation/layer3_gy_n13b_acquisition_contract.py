"""Recomputing frozen contract for the GY-N13b acquisition executor.

This plan-named module is an audit composer only.  Runtime authority remains in
the canonical acquisition passport/overlay owners, the Fabric evidence journal,
the DatasetCatalogGraph read path, and the derived-observation CAS machinery.
The composer binds their narrow projections without becoming a parallel owner.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.data_plane import (
    canonical_json_bytes,
    content_sha256,
    resolve_live_attempt_terminals,
    resolve_raw_response_body,
)
from tools.quality.validation.layer3_gy_acquisition_executor import (
    D6RouteSelection,
    MetadataProbeExecutionEvidence,
    R1ForensicReceipt,
)
from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
    CensusManifest,
    RecurringCarrierLivenessUpdate,
    semantic_content_hash,
)
from tools.quality.validation.layer3_gy_n13b_acceptance import (
    AcceptanceCaseReceipt,
    AcceptanceFallbackSelection,
    AcceptanceInputSelection,
    AcceptanceLiveExecutionReceipt,
    verify_persisted_acceptance_case,
)
from tools.quality.validation.layer3_gy_n13b_reentry import N13bReentryTrace

SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
N13B_FAMILY_ID = "policy-design-case-layer3-gy-n13b-acquisition-executor"
DEFAULT_N13B_CONTRACT = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_executor_contract.json"
)
DEFAULT_N13B_LIFECYCLE_MANIFEST = Path(
    "architecture/policy_design_case/layer3_gy_n13b_lifecycle_manifest.json"
)
DEFAULT_GENERATED_ARTIFACTS = Path("architecture/generated_artifacts.toml")
DEFAULT_N13B_JOURNAL = Path(
    "architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
)
DEFAULT_N13B_CAS = Path("architecture/policy_design_case/layer3_gy_acquisition_cas")
DEFAULT_N13B_PROVISION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_provision.json"
)
DEFAULT_N13B_REGISTRY = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_registry.json"
)
DEFAULT_DERIVED_ACCEPTANCE = Path(
    "architecture/policy_design_case/layer3_gy_n13b_derived_acceptance_case.json"
)
DEFAULT_N13A_CENSUS = Path("architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json")
DEFAULT_CARRIER_LIVENESS = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json"
)
DEFAULT_R1_FORENSIC = Path(
    "architecture/policy_design_case/layer3_gy_n13b_r1_forensic_receipt.json"
)
DEFAULT_R2_METADATA_EVIDENCE = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13b_worldbank_government_balance_metadata_evidence.json"
)
DEFAULT_D6_ROUTE = Path("architecture/policy_design_case/layer3_gy_n13b_d6_route_selection.json")
DEFAULT_R3_METADATA_EVIDENCE = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13b_worldbank_government_balance_percent_gdp_metadata_evidence.json"
)
DEFAULT_ACCEPTANCE_INPUTS = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acceptance_input_selection.json"
)
DEFAULT_ACCEPTANCE_EXECUTION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_cpi_live_execution_evidence.json"
)
DEFAULT_ACCEPTANCE_FALLBACK = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acceptance_fallback_selection.json"
)
DEFAULT_REENTRY_TRACE = Path("architecture/policy_design_case/layer3_gy_n13b_reentry_trace.json")
_SOURCE_OWNER_PATHS = (
    "src/polisyos/data_forge/domains/catalog/knowledge/acquisition_authority.py",
    "src/polisyos/data_forge/domains/catalog/knowledge/overlay.py",
    "src/polisyos/fabric/data_plane/evidence_journal.py",
    "src/polisyos/runtime/quality/acquisition_executor.py",
    "src/polisyos/runtime/quality/acquisition_planner.py",
    "src/polisyos/runtime/quality/data_state_substrate.py",
    "src/polisyos/runtime/quality/derived_observations.py",
)


class N13bContractError(RuntimeError):
    """Fail-closed N13b contract error with a stable code."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(f"{code}: {self.detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LocalLiftRefusalRow(_StrictModel):
    """One census residual evaluated against the canonical local-rights owner."""

    rank: int = Field(ge=1)
    variable_id: str = Field(min_length=1)
    gap_kind: Literal["binding_gap"]
    demand_sources: tuple[str, ...] = Field(min_length=1)
    admissible: bool
    rejection_codes: tuple[str, ...]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _row_is_content_bound(self) -> Self:
        if self.demand_sources != tuple(sorted(set(self.demand_sources))):
            raise ValueError("local-lift demand sources must be unique and sorted")
        if self.rejection_codes != tuple(sorted(set(self.rejection_codes))):
            raise ValueError("local-lift rejection codes must be unique and sorted")
        if self.admissible != (not self.rejection_codes):
            raise ValueError("local-lift admission must derive from owner rejection codes")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("local-lift row identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class LocalLiftRefusal(_StrictModel):
    """Full 15-row local-lift denominator and its honest terminal."""

    census_growth_backlog_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    provision_id: str = Field(pattern=r"^acquisition-authority-provision:sha256:[0-9a-f]{64}$")
    local_rights_trust_anchor_sha256: str | None = Field(
        default=None,
        pattern=SHA256_PATTERN,
    )
    rows: tuple[LocalLiftRefusalRow, ...] = Field(min_length=1)
    residual_denominator_count: int = Field(ge=1)
    admissible_count: int = Field(ge=0)
    disposition: Literal["no_admissible_local_binding", "local_lift_admissible"]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _disposition_is_recomputed(self) -> Self:
        ranks = tuple(row.rank for row in self.rows)
        if ranks != tuple(range(1, len(self.rows) + 1)):
            raise ValueError("local-lift rows must preserve the complete ranked denominator")
        if self.residual_denominator_count != len(self.rows):
            raise ValueError("local-lift denominator count drift")
        admissible = sum(row.admissible for row in self.rows)
        if self.admissible_count != admissible:
            raise ValueError("local-lift admissible count must be recomputed")
        expected = "local_lift_admissible" if admissible else "no_admissible_local_binding"
        if self.disposition != expected:
            raise ValueError("local-lift disposition must be recomputed")
        if self.local_rights_trust_anchor_sha256 is None and any(
            row.rejection_codes != ("local_rights_authority_unavailable",) for row in self.rows
        ):
            raise ValueError("absent local rights owner must fail every residual closed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("local-lift refusal identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


def derive_local_lift_refusal(
    *,
    census: CensusManifest,
    provision: catalog_read_api.AcquisitionAuthorityProvision,
) -> LocalLiftRefusal:
    """Evaluate every D2 residual against the independently owned rights root."""

    frozen_census = CensusManifest.model_validate(census.model_dump(mode="python"))
    frozen_provision = catalog_read_api.AcquisitionAuthorityProvision.model_validate(
        provision.model_dump(mode="python")
    )
    rows: list[LocalLiftRefusalRow] = []
    for backlog in frozen_census.growth_backlog:
        rejection_codes = (
            ("local_rights_authority_unavailable",)
            if frozen_provision.local_rights_trust_anchor_sha256 is None
            else ()
        )
        values = {
            "rank": backlog.rank,
            "variable_id": backlog.variable_id,
            "gap_kind": backlog.gap_kind.value,
            "demand_sources": backlog.demand_sources,
            "admissible": not rejection_codes,
            "rejection_codes": rejection_codes,
        }
        rows.append(
            LocalLiftRefusalRow(
                **values,
                projection_sha256=content_sha256(values),
            )
        )
    backlog_projection = [row.model_dump(mode="json") for row in frozen_census.growth_backlog]
    values = {
        "census_growth_backlog_projection_sha256": content_sha256(backlog_projection),
        "provision_id": frozen_provision.provision_id,
        "local_rights_trust_anchor_sha256": frozen_provision.local_rights_trust_anchor_sha256,
        "rows": tuple(rows),
        "residual_denominator_count": len(rows),
        "admissible_count": sum(row.admissible for row in rows),
        "disposition": (
            "local_lift_admissible"
            if any(row.admissible for row in rows)
            else "no_admissible_local_binding"
        ),
    }
    return LocalLiftRefusal(
        **values,
        projection_sha256=content_sha256(_json_value(values)),
    )


class LiveAttemptProjection(_StrictModel):
    """Path-stable journal/CAS projection for one paid live attempt."""

    attempt_id: str = Field(min_length=1)
    request_sequence: int = Field(ge=1)
    call_class: Literal["data_fetch", "indicator_metadata"]
    request_variables: tuple[str, ...] = Field(min_length=1, max_length=1)
    request_event_sha256: str = Field(pattern=SHA256_PATTERN)
    failure_code: str = Field(min_length=1)
    outcome_code: str = Field(min_length=1)
    terminal_sha256: str = Field(pattern=SHA256_PATTERN)
    raw_evidence_event_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    raw_body_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    raw_byte_count: int | None = Field(default=None, ge=0)
    raw_cas_persisted: bool
    http_status_code: int | None = Field(default=None, ge=100, le=599)
    quarantine: Literal[True]
    response_admitted: Literal[False]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _attempt_is_content_bound(self) -> Self:
        raw = (
            self.raw_evidence_event_sha256,
            self.raw_body_sha256,
            self.raw_byte_count,
        )
        if any(value is None for value in raw) != all(value is None for value in raw):
            raise ValueError("attempt raw evidence projection must be complete or absent")
        if self.raw_body_sha256 is None and self.raw_cas_persisted:
            raise ValueError("an absent raw response cannot claim CAS persistence")
        if self.raw_body_sha256 is not None and not self.raw_cas_persisted:
            raise ValueError("journaled raw response bytes must persist in quarantine CAS")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("live-attempt projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class JournalEvidenceProjection(_StrictModel):
    """Full journal denominator proving request/terminal/raw evidence persistence."""

    journal_ref: Literal[
        "repo://architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
    ]
    journal_byte_sha256: str = Field(pattern=SHA256_PATTERN)
    event_count: int = Field(ge=1)
    request_count: int = Field(ge=1)
    terminal_count: int = Field(ge=1)
    raw_response_count: int = Field(ge=0)
    persisted_raw_response_count: int = Field(ge=0)
    response_admitted_count: int = Field(ge=0)
    quarantine_count: int = Field(ge=0)
    attempts: tuple[LiveAttemptProjection, ...] = Field(min_length=1)
    journal_raw_evidence_persistence_missing_closed: bool
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _denominator_is_recomputed(self) -> Self:
        attempts = self.attempts
        if tuple(row.request_sequence for row in attempts) != tuple(
            sorted(row.request_sequence for row in attempts)
        ):
            raise ValueError("live attempts must preserve journal request order")
        if len({row.attempt_id for row in attempts}) != len(attempts):
            raise ValueError("live attempt denominator contains duplicates")
        expected_raw = sum(row.raw_body_sha256 is not None for row in attempts)
        expected_persisted = sum(row.raw_cas_persisted for row in attempts)
        expected_admitted = sum(row.response_admitted for row in attempts)
        expected_quarantine = sum(row.quarantine for row in attempts)
        if (
            self.request_count != len(attempts)
            or self.terminal_count != len(attempts)
            or self.raw_response_count != expected_raw
            or self.persisted_raw_response_count != expected_persisted
            or self.response_admitted_count != expected_admitted
            or self.quarantine_count != expected_quarantine
        ):
            raise ValueError("journal evidence counts must cover the complete attempt denominator")
        expected_closed = (
            self.request_count == self.terminal_count
            and self.raw_response_count == self.persisted_raw_response_count
            and self.response_admitted_count == 0
        )
        if self.journal_raw_evidence_persistence_missing_closed != expected_closed:
            raise ValueError("journal persistence residual must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("journal projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


def derive_journal_evidence_projection(
    *,
    journal_path: Path,
    cas_root: Path,
) -> JournalEvidenceProjection:
    """Reopen every exact request/terminal and bind raw bytes into quarantine CAS."""

    journal = Path(journal_path)
    events = _read_canonical_jsonl(journal)
    terminals = resolve_live_attempt_terminals(journal)
    requests = {
        int(event["sequence"]): event for event in events if event.get("event_kind") == "request"
    }
    if len(requests) != len(terminals):
        raise N13bContractError("journal_attempt_denominator_incomplete")
    rows: list[LiveAttemptProjection] = []
    for terminal in terminals:
        request_event = requests.get(terminal.request_ref.sequence)
        if request_event is None or request_event.get("attempt_id") != terminal.attempt_id:
            raise N13bContractError("journal_terminal_request_unresolved", terminal.attempt_id)
        request = request_event.get("request")
        if not isinstance(request, dict):
            raise N13bContractError("journal_request_payload_invalid", terminal.attempt_id)
        request_variables = request.get("request_variables")
        if not isinstance(request_variables, list) or len(request_variables) != 1:
            raise N13bContractError("journal_request_variable_budget_drift", terminal.attempt_id)
        call_class = (
            "indicator_metadata"
            if request.get("call_class") == "indicator_metadata"
            else "data_fetch"
        )
        raw_body: bytes | None = None
        raw_body_sha: str | None = None
        raw_byte_count: int | None = None
        raw_event_sha: str | None = None
        raw_persisted = False
        if terminal.raw_evidence_ref is not None:
            raw_body = resolve_raw_response_body(terminal.raw_evidence_ref)
            raw_body_sha = _bytes_sha256(raw_body)
            raw_byte_count = len(raw_body)
            raw_event_sha = terminal.raw_evidence_ref.event_sha256
            blob = _cas_blob_path(Path(cas_root), raw_body_sha)
            raw_persisted = blob.is_file() and _file_sha256(blob) == raw_body_sha
        values = {
            "attempt_id": terminal.attempt_id,
            "request_sequence": terminal.request_ref.sequence,
            "call_class": call_class,
            "request_variables": tuple(str(value) for value in request_variables),
            "request_event_sha256": terminal.request_ref.event_sha256,
            "failure_code": terminal.failure_code,
            "outcome_code": terminal.outcome_code,
            "terminal_sha256": terminal.terminal_sha256,
            "raw_evidence_event_sha256": raw_event_sha,
            "raw_body_sha256": raw_body_sha,
            "raw_byte_count": raw_byte_count,
            "raw_cas_persisted": raw_persisted,
            "http_status_code": terminal.http_status_code,
            "quarantine": terminal.quarantine,
            "response_admitted": terminal.response_admitted,
        }
        rows.append(
            LiveAttemptProjection(
                **values,
                projection_sha256=content_sha256(values),
            )
        )
    values = {
        "journal_ref": (
            "repo://architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
        ),
        "journal_byte_sha256": _file_sha256(journal),
        "event_count": len(events),
        "request_count": len(requests),
        "terminal_count": len(terminals),
        "raw_response_count": sum(row.raw_body_sha256 is not None for row in rows),
        "persisted_raw_response_count": sum(row.raw_cas_persisted for row in rows),
        "response_admitted_count": sum(row.response_admitted for row in rows),
        "quarantine_count": sum(row.quarantine for row in rows),
        "attempts": tuple(rows),
        "journal_raw_evidence_persistence_missing_closed": (
            len(requests) == len(terminals)
            and all(row.raw_body_sha256 is None or row.raw_cas_persisted for row in rows)
            and not any(row.response_admitted for row in rows)
        ),
    }
    return JournalEvidenceProjection(
        **values,
        projection_sha256=content_sha256(_json_value(values)),
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


class LifecycleRegistration(_StrictModel):
    """One exact output row from the generated-artifact family denominator."""

    path: str = Field(min_length=1)
    role: Literal[
        "writer_managed",
        "journal",
        "cas_blob",
        "cas_manifest",
        "provision",
        "registry",
        "receipt",
    ]
    registration_status: Literal["writer_managed", "content_bound"]
    byte_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    byte_size: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _registration_is_well_formed(self) -> Self:
        if self.registration_status == "writer_managed":
            if self.role != "writer_managed" or self.byte_sha256 is not None:
                raise ValueError("writer-managed outputs cannot self-bind content")
        elif self.role == "writer_managed" or self.byte_sha256 is None or self.byte_size is None:
            raise ValueError("content-bound lifecycle output is incomplete")
        return self


class N13bLifecycleManifest(_StrictModel):
    """Acyclic lifecycle registration for all materialized N13b outputs."""

    schema_version: Literal["policyos.layer3.gy.n13b.lifecycle_manifest.v1"] = (
        "policyos.layer3.gy.n13b.lifecycle_manifest.v1"
    )
    generated_family_id: Literal["policy-design-case-layer3-gy-n13b-acquisition-executor"]
    generated_family_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    registrations: tuple[LifecycleRegistration, ...] = Field(min_length=1)
    registered_output_count: int = Field(ge=1)
    content_bound_output_count: int = Field(ge=1)
    phantom_output_count: int = Field(ge=0)
    materialized_acquired_snapshot_count: int = Field(ge=0)
    registered_acquired_snapshot_count: int = Field(ge=0)
    canonical_provision_registered: bool
    derived_artifact_registered: bool
    derivation_certificate_registered: bool
    owner_registration_derivation_missing_closed: bool
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _closure_is_recomputed(self) -> Self:
        paths = tuple(row.path for row in self.registrations)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("lifecycle output denominator must be unique and sorted")
        content_bound = sum(
            row.registration_status == "content_bound" for row in self.registrations
        )
        if (
            self.registered_output_count != len(self.registrations)
            or self.content_bound_output_count != content_bound
        ):
            raise ValueError("lifecycle registration counts must be recomputed")
        expected_closed = (
            self.phantom_output_count == 0
            and self.materialized_acquired_snapshot_count == self.registered_acquired_snapshot_count
            and self.canonical_provision_registered
            and self.derived_artifact_registered
            and self.derivation_certificate_registered
        )
        if self.owner_registration_derivation_missing_closed != expected_closed:
            raise ValueError("owner-registration residual must be recomputed")
        if self.manifest_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("lifecycle manifest identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        value = {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "manifest_sha256"
        }
        value["registrations"] = [
            {
                "path": row.path,
                "role": row.role,
                "registration_status": row.registration_status,
            }
            for row in self.registrations
        ]
        return value


def derive_lifecycle_manifest(repo_root: Path) -> N13bLifecycleManifest:
    """Derive lifecycle registrations from the real generated-artifact family."""

    root = Path(repo_root)
    generated_path = root / DEFAULT_GENERATED_ARTIFACTS
    try:
        payload = tomllib.loads(generated_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise N13bContractError("generated_artifact_registry_unreadable") from exc
    families = [
        row
        for row in payload.get("family", [])
        if isinstance(row, dict) and row.get("id") == N13B_FAMILY_ID
    ]
    if len(families) != 1:
        raise N13bContractError("n13b_generated_family_unresolved")
    family = families[0]
    output_values = family.get("outputs")
    if not isinstance(output_values, list) or not output_values:
        raise N13bContractError("n13b_generated_outputs_missing")
    outputs = tuple(sorted(str(value) for value in output_values))
    if len(outputs) != len(set(outputs)):
        raise N13bContractError("n13b_generated_outputs_duplicate")
    writer_paths = {
        DEFAULT_N13B_CONTRACT.as_posix(),
        DEFAULT_N13B_LIFECYCLE_MANIFEST.as_posix(),
    }
    registrations: list[LifecycleRegistration] = []
    phantom = 0
    for relative in outputs:
        path = root / relative
        if relative in writer_paths:
            registrations.append(
                LifecycleRegistration(
                    path=relative,
                    role="writer_managed",
                    registration_status="writer_managed",
                    byte_sha256=None,
                    byte_size=None,
                )
            )
            continue
        if not path.is_file():
            phantom += 1
            continue
        registrations.append(
            LifecycleRegistration(
                path=relative,
                role=_lifecycle_role(relative),
                registration_status="content_bound",
                byte_sha256=_file_sha256(path),
                byte_size=path.stat().st_size,
            )
        )
    registration_paths = {row.path for row in registrations}
    derived_path = _cas_blob_relative(
        "sha256:6f8bf2cfc76b89da8500b827c46237fcba4d22fa34fe4b3a569c42156991cb34"
    )
    certificate_path = _cas_blob_relative(
        "sha256:2762950fb0162d50ee54af9947960a85db3b5ff80686f26a99f791726b9f0c0d"
    )
    snapshots = tuple(
        path
        for path in outputs
        if "snapshot" in Path(path).name or "overlay.duckdb" in Path(path).name
    )
    materialized_snapshots = tuple(path for path in snapshots if (root / path).is_file())
    family_projection = {
        key: family.get(key)
        for key in (
            "id",
            "lifecycle",
            "gy_lifecycle_family",
            "generator",
            "verifier",
            "promotion_target",
            "stale_output_behavior",
            "source_of_truth",
            "outputs",
            "regenerate_commands",
            "workflow",
            "check_command",
        )
    }
    values = {
        "schema_version": "policyos.layer3.gy.n13b.lifecycle_manifest.v1",
        "generated_family_id": N13B_FAMILY_ID,
        "generated_family_projection_sha256": content_sha256(family_projection),
        "registrations": tuple(sorted(registrations, key=lambda row: row.path)),
        "registered_output_count": len(registrations),
        "content_bound_output_count": sum(
            row.registration_status == "content_bound" for row in registrations
        ),
        "phantom_output_count": phantom,
        "materialized_acquired_snapshot_count": len(materialized_snapshots),
        "registered_acquired_snapshot_count": sum(
            path in registration_paths for path in materialized_snapshots
        ),
        "canonical_provision_registered": DEFAULT_N13B_PROVISION.as_posix() in registration_paths,
        "derived_artifact_registered": derived_path in registration_paths,
        "derivation_certificate_registered": certificate_path in registration_paths,
        "owner_registration_derivation_missing_closed": False,
    }
    values["owner_registration_derivation_missing_closed"] = (
        phantom == 0
        and len(materialized_snapshots)
        == sum(path in registration_paths for path in materialized_snapshots)
        and values["canonical_provision_registered"]
        and values["derived_artifact_registered"]
        and values["derivation_certificate_registered"]
    )
    identity = _json_value(values)
    identity["registrations"] = [
        {
            "path": row.path,
            "role": row.role,
            "registration_status": row.registration_status,
        }
        for row in values["registrations"]
    ]
    return N13bLifecycleManifest(**values, manifest_sha256=content_sha256(identity))


class EvidenceBinding(_StrictModel):
    """One validated source receipt with semantic and byte identities separated."""

    path: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    content_identity: str = Field(min_length=1)
    file_sha256: str = Field(pattern=SHA256_PATTERN)
    byte_size: int = Field(ge=1)


class SourceOwnerBinding(_StrictModel):
    """Exact committed source owner participating in the executor chain."""

    path: str = Field(min_length=1)
    file_sha256: str = Field(pattern=SHA256_PATTERN)
    byte_size: int = Field(ge=1)


class AuthorityOwnerProjection(_StrictModel):
    """Canonical acquisition provision/registry projection."""

    baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    l5_measurement_registry_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_content_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_entry_count: int = Field(ge=1)
    provision_id: str = Field(pattern=r"^acquisition-authority-provision:sha256:[0-9a-f]{64}$")
    live_harness_receipt_count: int = Field(ge=1)
    local_rights_trust_anchor_sha256: str | None = Field(
        default=None,
        pattern=SHA256_PATTERN,
    )
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _projection_is_content_bound(self) -> Self:
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("acquisition authority projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class CarrierLivenessProjection(_StrictModel):
    """D3 carrier disposition and tier-decay projection from the recurring owner."""

    connector_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    execution_tier: str = Field(min_length=1)
    data_disposition: str = Field(min_length=1)
    metadata_disposition: str = Field(min_length=1)
    carrier_disposition: str = Field(min_length=1)
    data_attempt_count: int = Field(ge=1)
    metadata_attempt_count: int = Field(ge=0, le=1)
    tier_decay_findings: tuple[str, ...]
    source_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _projection_is_content_bound(self) -> Self:
        if self.tier_decay_findings != tuple(sorted(set(self.tier_decay_findings))):
            raise ValueError("tier-decay findings must be unique and sorted")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("carrier liveness projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class ReentryProjection(_StrictModel):
    """Narrow real N7/catalog/runtime availability re-entry result."""

    target_variable: str = Field(min_length=1)
    trace_sha256: str = Field(pattern=SHA256_PATTERN)
    availability_count_before: int = Field(ge=0)
    availability_count_after: int = Field(ge=0)
    availability_count_delta: int
    overlay_epoch_count: int = Field(ge=0)
    overlay_admitted_observation_count: int = Field(ge=0)
    fetch_plan_count: int = Field(ge=0)
    fetch_plan_execution_count: Literal[0]
    reentry_disposition: str = Field(min_length=1)
    world_growth_status: Literal["grew", "no_growth"]
    world_growth_event_count: int = Field(ge=0, le=1)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _growth_is_recomputed(self) -> Self:
        if self.availability_count_delta != (
            self.availability_count_after - self.availability_count_before
        ):
            raise ValueError("re-entry availability delta drift")
        expected_count = int(
            self.availability_count_delta > 0
            and self.overlay_admitted_observation_count > 0
            and self.overlay_epoch_count > 0
        )
        if self.world_growth_event_count != expected_count or self.world_growth_status != (
            "grew" if expected_count else "no_growth"
        ):
            raise ValueError("re-entry world growth must derive from runtime availability")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("re-entry projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class QuarantineProjection(_StrictModel):
    """What arrived but did not enter the canonical observation overlay."""

    live_attempt_count: int = Field(ge=1)
    raw_response_count: int = Field(ge=0)
    terminal_without_response_count: int = Field(ge=0)
    response_admitted_count: int = Field(ge=0)
    overlay_admitted_observation_count: int = Field(ge=0)
    failure_code_counts: dict[str, int]
    disposition: Literal["all_live_evidence_quarantined_or_terminal", "admitted"]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _disposition_is_recomputed(self) -> Self:
        if any(value < 0 for value in self.failure_code_counts.values()):
            raise ValueError("quarantine failure counts must be nonnegative")
        if sum(self.failure_code_counts.values()) != self.live_attempt_count:
            raise ValueError("quarantine reasons must cover every attempt")
        if self.raw_response_count + self.terminal_without_response_count != (
            self.live_attempt_count
        ):
            raise ValueError("quarantine response denominator drift")
        admitted = self.response_admitted_count + self.overlay_admitted_observation_count
        expected = "admitted" if admitted else "all_live_evidence_quarantined_or_terminal"
        if self.disposition != expected:
            raise ValueError("quarantine disposition must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("quarantine projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class WorldGrowthProjection(_StrictModel):
    """True acquisition world-growth outcome, including honest zero."""

    target_variable: str = Field(min_length=1)
    availability_count_before: int = Field(ge=0)
    availability_count_after: int = Field(ge=0)
    availability_count_delta: int
    overlay_epoch_count: int = Field(ge=0)
    admitted_observation_count: int = Field(ge=0)
    event_count: int = Field(ge=0, le=1)
    status: Literal["grew", "no_growth"]
    terminal_disposition: str = Field(min_length=1)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _status_is_recomputed(self) -> Self:
        if self.availability_count_delta != (
            self.availability_count_after - self.availability_count_before
        ):
            raise ValueError("world-growth availability delta drift")
        expected = int(
            self.availability_count_delta > 0
            and self.overlay_epoch_count > 0
            and self.admitted_observation_count > 0
        )
        if self.event_count != expected or self.status != ("grew" if expected else "no_growth"):
            raise ValueError("world-growth status must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("world-growth projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class ResumptionBudgetProjection(_StrictModel):
    """Hard six-call resumption budget derived from the three source receipts."""

    maximum_call_count: Literal[6]
    spent_attempt_ids: tuple[str, ...]
    spent_call_count: int = Field(ge=0, le=6)
    remaining_call_count: int = Field(ge=0, le=6)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _budget_is_recomputed(self) -> Self:
        if self.spent_attempt_ids != tuple(sorted(set(self.spent_attempt_ids))):
            raise ValueError("resumption attempts must be unique and sorted")
        if self.spent_call_count != len(self.spent_attempt_ids) or self.remaining_call_count != (
            self.maximum_call_count - self.spent_call_count
        ):
            raise ValueError("resumption call budget must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("resumption budget identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class ResidualClosureProjection(_StrictModel):
    """The two N10 lifecycle/journal residuals closed by their real owners."""

    owner_registration_derivation_missing_closed: bool
    journal_raw_evidence_persistence_missing_closed: bool
    open_residuals: tuple[str, ...]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _residuals_are_recomputed(self) -> Self:
        expected = tuple(
            name
            for name, closed in (
                (
                    "journal_raw_evidence_persistence_missing",
                    self.journal_raw_evidence_persistence_missing_closed,
                ),
                (
                    "owner_registration_derivation_missing",
                    self.owner_registration_derivation_missing_closed,
                ),
            )
            if not closed
        )
        if self.open_residuals != expected:
            raise ValueError("N10 residual closure must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("residual closure identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class N13bAcquisitionExecutorContract(_StrictModel):
    """Frozen N13b contract recomputed from canonical data-plane owners."""

    schema_version: Literal["policyos.layer3.gy.n13b.acquisition_executor_contract.v1"] = (
        "policyos.layer3.gy.n13b.acquisition_executor_contract.v1"
    )
    rule_version: Literal["GY-plan-rev18+3.5.12-D1-D6"]
    producer: Literal[
        "tools.quality.validation.layer3_gy_n13b_acquisition_contract."
        "derive_n13b_acquisition_executor_contract"
    ]
    baseline_ref: Literal[
        "repo://production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
    ]
    baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    l5_measurement_registry_sha256: str = Field(pattern=SHA256_PATTERN)
    source_owners: tuple[SourceOwnerBinding, ...] = Field(min_length=1)
    evidence_bindings: tuple[EvidenceBinding, ...] = Field(min_length=1)
    authority_owner: AuthorityOwnerProjection
    local_lift: LocalLiftRefusal
    journal: JournalEvidenceProjection
    carrier_liveness: CarrierLivenessProjection
    derivation: DerivationProjection
    reentry: ReentryProjection
    capstone_routes: CapstoneRoutePreservation
    lifecycle: N13bLifecycleManifest
    quarantine: QuarantineProjection
    world_growth: WorldGrowthProjection
    resumption_budget: ResumptionBudgetProjection
    residual_closure: ResidualClosureProjection
    executor_capability_status: Literal["implemented"]
    demonstration_status: Literal["world_growth_observed", "typed_deeper_terminal"]
    surface_status: Literal["audit_surface"]
    pattern_pass: tuple[
        Literal["P05", "P10", "P27", "P29", "P31", "P32", "P33", "P34"],
        ...,
    ]
    contract_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _contract_is_recomputed(self) -> Self:
        source_paths = tuple(row.path for row in self.source_owners)
        if source_paths != tuple(sorted(set(source_paths))):
            raise ValueError("source-owner denominator must be unique and sorted")
        evidence_paths = tuple(row.path for row in self.evidence_bindings)
        if evidence_paths != tuple(sorted(set(evidence_paths))):
            raise ValueError("evidence-binding denominator must be unique and sorted")
        if (
            self.baseline_sha256 != self.authority_owner.baseline_sha256
            or self.l5_measurement_registry_sha256
            != self.authority_owner.l5_measurement_registry_sha256
        ):
            raise ValueError("contract baseline/L5 identity drift")
        if (
            self.world_growth.target_variable != self.reentry.target_variable
            or self.world_growth.availability_count_delta != self.reentry.availability_count_delta
            or self.world_growth.overlay_epoch_count != self.reentry.overlay_epoch_count
            or self.world_growth.admitted_observation_count
            != self.reentry.overlay_admitted_observation_count
            or self.world_growth.event_count != self.reentry.world_growth_event_count
            or self.world_growth.status != self.reentry.world_growth_status
            or self.world_growth.terminal_disposition != self.reentry.reentry_disposition
        ):
            raise ValueError("world-growth receipt must preserve the real re-entry trace")
        expected_demo = (
            "world_growth_observed" if self.world_growth.event_count else "typed_deeper_terminal"
        )
        if self.demonstration_status != expected_demo:
            raise ValueError("demonstration status must derive from true world growth")
        if self.capstone_routes.laundered_route_count != 0:
            raise ValueError("N13b cannot launder structural capstone routes")
        if (
            self.residual_closure.owner_registration_derivation_missing_closed
            != self.lifecycle.owner_registration_derivation_missing_closed
            or self.residual_closure.journal_raw_evidence_persistence_missing_closed
            != self.journal.journal_raw_evidence_persistence_missing_closed
        ):
            raise ValueError("residual closure must bind lifecycle and journal owners")
        if self.pattern_pass != tuple(sorted(set(self.pattern_pass))):
            raise ValueError("pattern pass must be unique and sorted")
        if self.contract_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("N13b contract identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return timestamp-free semantic evidence without byte-only lifecycle fields."""

        value = self.model_dump(mode="json")
        value.pop("contract_sha256", None)
        value["source_owners"] = [
            {"path": row.path, "file_sha256": row.file_sha256} for row in self.source_owners
        ]
        value["evidence_bindings"] = [
            {
                "path": row.path,
                "schema_version": row.schema_version,
                "content_identity": row.content_identity,
            }
            for row in self.evidence_bindings
        ]
        value["lifecycle"] = self.lifecycle.identity_payload()
        return value


def derive_n13b_acquisition_executor_contract(
    *,
    repo_root: Path,
    baseline_sha256: str,
    l5_sha256: str,
) -> N13bAcquisitionExecutorContract:
    """Recompute the frozen N13b contract without any network or engine execution."""

    root = Path(repo_root)
    census = _read_model(root / DEFAULT_N13A_CENSUS, CensusManifest)
    provision = _read_model(
        root / DEFAULT_N13B_PROVISION,
        catalog_read_api.AcquisitionAuthorityProvision,
    )
    registry = _read_model(
        root / DEFAULT_N13B_REGISTRY,
        catalog_read_api.AcquisitionAuthorityRegistry,
    )
    r1 = _read_model(root / DEFAULT_R1_FORENSIC, R1ForensicReceipt)
    carrier = _read_model(
        root / DEFAULT_CARRIER_LIVENESS,
        RecurringCarrierLivenessUpdate,
    )
    r2 = _read_model(
        root / DEFAULT_R2_METADATA_EVIDENCE,
        MetadataProbeExecutionEvidence,
    )
    d6 = _read_model(root / DEFAULT_D6_ROUTE, D6RouteSelection)
    r3 = _read_model(
        root / DEFAULT_R3_METADATA_EVIDENCE,
        MetadataProbeExecutionEvidence,
    )
    acceptance_inputs = _read_model(
        root / DEFAULT_ACCEPTANCE_INPUTS,
        AcceptanceInputSelection,
    )
    acceptance_live = _read_model(
        root / DEFAULT_ACCEPTANCE_EXECUTION,
        AcceptanceLiveExecutionReceipt,
    )
    acceptance_fallback = _read_model(
        root / DEFAULT_ACCEPTANCE_FALLBACK,
        AcceptanceFallbackSelection,
    )
    acceptance = _read_model(root / DEFAULT_DERIVED_ACCEPTANCE, AcceptanceCaseReceipt)
    reentry = _read_model(root / DEFAULT_REENTRY_TRACE, N13bReentryTrace)
    if (
        baseline_sha256 != provision.baseline_content_sha256
        or baseline_sha256 != registry.baseline_content_sha256
        or baseline_sha256 != reentry.baseline_sha256
        or l5_sha256 != registry.l5_measurement_registry_sha256
        or l5_sha256 != provision.l5_measurement_registry_content_sha256
    ):
        raise N13bContractError("n13b_baseline_or_l5_owner_drift")
    lifecycle = derive_lifecycle_manifest(root)
    journal = derive_journal_evidence_projection(
        journal_path=root / DEFAULT_N13B_JOURNAL,
        cas_root=root / DEFAULT_N13B_CAS,
    )
    local_lift = derive_local_lift_refusal(census=census, provision=provision)
    derivation = derive_derivation_projection(
        acceptance=acceptance,
        cas_root=root / DEFAULT_N13B_CAS,
    )
    capstone = derive_capstone_route_preservation(census)
    authority_values = {
        "baseline_sha256": provision.baseline_content_sha256,
        "l5_measurement_registry_sha256": (provision.l5_measurement_registry_content_sha256),
        "registry_content_sha256": registry.content_sha256,
        "registry_entry_count": len(registry.entries),
        "provision_id": provision.provision_id,
        "live_harness_receipt_count": len(provision.live_harness_receipts),
        "local_rights_trust_anchor_sha256": provision.local_rights_trust_anchor_sha256,
    }
    authority = AuthorityOwnerProjection(
        **authority_values,
        projection_sha256=content_sha256(authority_values),
    )
    carrier_values = {
        "connector_id": carrier.connector_id,
        "request_dataset_id": carrier.request_dataset_id,
        "execution_tier": carrier.execution_tier,
        "data_disposition": carrier.data_disposition.value,
        "metadata_disposition": carrier.metadata_disposition.value,
        "carrier_disposition": carrier.carrier_disposition.value,
        "data_attempt_count": len(carrier.data_attempts),
        "metadata_attempt_count": int(carrier.metadata_attempt is not None),
        "tier_decay_findings": carrier.tier_decay_findings,
        "source_receipt_sha256": carrier.receipt_sha256,
    }
    carrier_projection = CarrierLivenessProjection(
        **carrier_values,
        projection_sha256=content_sha256(carrier_values),
    )
    reentry_values = {
        "target_variable": reentry.target_variable,
        "trace_sha256": reentry.trace_sha256,
        "availability_count_before": reentry.availability_count_before,
        "availability_count_after": reentry.availability_count_after,
        "availability_count_delta": reentry.availability_count_delta,
        "overlay_epoch_count": reentry.overlay_state.epoch_count,
        "overlay_admitted_observation_count": (reentry.overlay_state.admitted_observation_count),
        "fetch_plan_count": reentry.catalog_resolution.fetch_plan_count,
        "fetch_plan_execution_count": (reentry.catalog_resolution.fetch_plan_execution_count),
        "reentry_disposition": reentry.reentry_disposition,
        "world_growth_status": reentry.world_growth_status,
        "world_growth_event_count": reentry.world_growth_event_count,
    }
    reentry_projection = ReentryProjection(
        **reentry_values,
        projection_sha256=content_sha256(reentry_values),
    )
    failure_counts: dict[str, int] = {}
    for attempt in journal.attempts:
        failure_counts[attempt.failure_code] = failure_counts.get(attempt.failure_code, 0) + 1
    quarantine_values = {
        "live_attempt_count": journal.terminal_count,
        "raw_response_count": journal.raw_response_count,
        "terminal_without_response_count": (journal.terminal_count - journal.raw_response_count),
        "response_admitted_count": journal.response_admitted_count,
        "overlay_admitted_observation_count": (reentry.overlay_state.admitted_observation_count),
        "failure_code_counts": dict(sorted(failure_counts.items())),
        "disposition": (
            "admitted"
            if journal.response_admitted_count or reentry.overlay_state.admitted_observation_count
            else "all_live_evidence_quarantined_or_terminal"
        ),
    }
    quarantine = QuarantineProjection(
        **quarantine_values,
        projection_sha256=content_sha256(quarantine_values),
    )
    world_values = {
        "target_variable": reentry.target_variable,
        "availability_count_before": reentry.availability_count_before,
        "availability_count_after": reentry.availability_count_after,
        "availability_count_delta": reentry.availability_count_delta,
        "overlay_epoch_count": reentry.overlay_state.epoch_count,
        "admitted_observation_count": reentry.overlay_state.admitted_observation_count,
        "event_count": reentry.world_growth_event_count,
        "status": reentry.world_growth_status,
        "terminal_disposition": reentry.reentry_disposition,
    }
    world_growth = WorldGrowthProjection(
        **world_values,
        projection_sha256=content_sha256(world_values),
    )
    resumption_ids = tuple(sorted({r2.attempt_id, r3.attempt_id, acceptance_live.attempt_id}))
    budget_values = {
        "maximum_call_count": 6,
        "spent_attempt_ids": resumption_ids,
        "spent_call_count": len(resumption_ids),
        "remaining_call_count": 6 - len(resumption_ids),
    }
    budget = ResumptionBudgetProjection(
        **budget_values,
        projection_sha256=content_sha256(budget_values),
    )
    closure_values = {
        "owner_registration_derivation_missing_closed": (
            lifecycle.owner_registration_derivation_missing_closed
        ),
        "journal_raw_evidence_persistence_missing_closed": (
            journal.journal_raw_evidence_persistence_missing_closed
        ),
    }
    closure_values["open_residuals"] = tuple(
        name
        for name, closed in (
            (
                "journal_raw_evidence_persistence_missing",
                closure_values["journal_raw_evidence_persistence_missing_closed"],
            ),
            (
                "owner_registration_derivation_missing",
                closure_values["owner_registration_derivation_missing_closed"],
            ),
        )
        if not closed
    )
    closure = ResidualClosureProjection(
        **closure_values,
        projection_sha256=content_sha256(closure_values),
    )
    models_and_identities: tuple[tuple[Path, BaseModel, str], ...] = (
        (DEFAULT_N13A_CENSUS, census, semantic_content_hash(census)),
        (DEFAULT_N13B_PROVISION, provision, provision.provision_id),
        (DEFAULT_N13B_REGISTRY, registry, registry.content_sha256),
        (DEFAULT_R1_FORENSIC, r1, r1.receipt_sha256),
        (DEFAULT_CARRIER_LIVENESS, carrier, carrier.receipt_sha256),
        (DEFAULT_R2_METADATA_EVIDENCE, r2, r2.evidence_sha256),
        (DEFAULT_D6_ROUTE, d6, d6.selection_sha256),
        (DEFAULT_R3_METADATA_EVIDENCE, r3, r3.evidence_sha256),
        (DEFAULT_ACCEPTANCE_INPUTS, acceptance_inputs, acceptance_inputs.selection_sha256),
        (DEFAULT_ACCEPTANCE_EXECUTION, acceptance_live, acceptance_live.receipt_sha256),
        (
            DEFAULT_ACCEPTANCE_FALLBACK,
            acceptance_fallback,
            acceptance_fallback.selection_sha256,
        ),
        (DEFAULT_DERIVED_ACCEPTANCE, acceptance, acceptance.receipt_sha256),
        (DEFAULT_REENTRY_TRACE, reentry, reentry.trace_sha256),
    )
    evidence_bindings = tuple(
        sorted(
            (
                _evidence_binding(root, path, model, identity)
                for path, model, identity in models_and_identities
            ),
            key=lambda row: row.path,
        )
    )
    source_owners = tuple(
        SourceOwnerBinding(
            path=path,
            file_sha256=_file_sha256(root / path),
            byte_size=(root / path).stat().st_size,
        )
        for path in _SOURCE_OWNER_PATHS
    )
    values = {
        "schema_version": "policyos.layer3.gy.n13b.acquisition_executor_contract.v1",
        "rule_version": "GY-plan-rev18+3.5.12-D1-D6",
        "producer": (
            "tools.quality.validation.layer3_gy_n13b_acquisition_contract."
            "derive_n13b_acquisition_executor_contract"
        ),
        "baseline_ref": (
            "repo://production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
        ),
        "baseline_sha256": baseline_sha256,
        "l5_measurement_registry_sha256": l5_sha256,
        "source_owners": source_owners,
        "evidence_bindings": evidence_bindings,
        "authority_owner": authority,
        "local_lift": local_lift,
        "journal": journal,
        "carrier_liveness": carrier_projection,
        "derivation": derivation,
        "reentry": reentry_projection,
        "capstone_routes": capstone,
        "lifecycle": lifecycle,
        "quarantine": quarantine,
        "world_growth": world_growth,
        "resumption_budget": budget,
        "residual_closure": closure,
        "executor_capability_status": "implemented",
        "demonstration_status": (
            "world_growth_observed" if world_growth.event_count else "typed_deeper_terminal"
        ),
        "surface_status": "audit_surface",
        "pattern_pass": ("P05", "P10", "P27", "P29", "P31", "P32", "P33", "P34"),
    }
    identity = _json_value(values)
    identity["source_owners"] = [
        {"path": row.path, "file_sha256": row.file_sha256} for row in source_owners
    ]
    identity["evidence_bindings"] = [
        {
            "path": row.path,
            "schema_version": row.schema_version,
            "content_identity": row.content_identity,
        }
        for row in evidence_bindings
    ]
    identity["lifecycle"] = lifecycle.identity_payload()
    return N13bAcquisitionExecutorContract(
        **values,
        contract_sha256=content_sha256(identity),
    )


def _read_model(path: Path, model: type[BaseModel]) -> Any:
    try:
        return model.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise N13bContractError("n13b_source_artifact_invalid", path.as_posix()) from exc


def _evidence_binding(
    root: Path,
    relative: Path,
    model: BaseModel,
    identity: str,
) -> EvidenceBinding:
    path = root / relative
    schema_version = getattr(model, "schema_version", None)
    if not isinstance(schema_version, str):
        raise N13bContractError("n13b_source_schema_version_missing", relative.as_posix())
    return EvidenceBinding(
        path=relative.as_posix(),
        schema_version=schema_version,
        content_identity=identity,
        file_sha256=_file_sha256(path),
        byte_size=path.stat().st_size,
    )


def _lifecycle_role(
    path: str,
) -> Literal[
    "journal",
    "cas_blob",
    "cas_manifest",
    "provision",
    "registry",
    "receipt",
]:
    if path.endswith(".jsonl"):
        return "journal"
    if path.endswith(".blob"):
        return "cas_blob"
    if path.endswith(".manifest.json"):
        return "cas_manifest"
    if path == DEFAULT_N13B_PROVISION.as_posix():
        return "provision"
    if path == DEFAULT_N13B_REGISTRY.as_posix():
        return "registry"
    return "receipt"


def _read_canonical_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    payload = path.read_bytes()
    if not payload.endswith(b"\n"):
        raise N13bContractError("journal_not_newline_terminated")
    events: list[dict[str, Any]] = []
    for expected_sequence, line in enumerate(payload.splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise N13bContractError("journal_event_invalid") from exc
        if not isinstance(event, dict) or event.get("sequence") != expected_sequence:
            raise N13bContractError("journal_event_sequence_drift")
        if canonical_json_bytes(event).rstrip(b"\n") != line:
            raise N13bContractError("journal_event_not_canonical")
        events.append(event)
    return tuple(events)


def _cas_blob_path(cas_root: Path, artifact_id: str) -> Path:
    digest = artifact_id.removeprefix("sha256:")
    return Path(cas_root) / "artifacts/sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"


def _cas_blob_relative(artifact_id: str) -> str:
    digest = artifact_id.removeprefix("sha256:")
    return (
        DEFAULT_N13B_CAS / "artifacts/sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"
    ).as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _bytes_sha256(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    return value


__all__ = [
    "DEFAULT_N13B_CONTRACT",
    "DEFAULT_N13B_LIFECYCLE_MANIFEST",
    "CapstoneRoutePreservation",
    "DerivationProjection",
    "JournalEvidenceProjection",
    "LocalLiftRefusal",
    "N13bAcquisitionExecutorContract",
    "N13bContractError",
    "N13bLifecycleManifest",
    "derive_capstone_route_preservation",
    "derive_derivation_projection",
    "derive_journal_evidence_projection",
    "derive_lifecycle_manifest",
    "derive_local_lift_refusal",
    "derive_n13b_acquisition_executor_contract",
]
