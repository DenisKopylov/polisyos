"""Canonical owner resolution for acquisition admission.

The acquisition registry may extend the catalog with last-mile field edges, but
it cannot mint source, license, L5, or transport authority.  Those properties
are re-resolved from the immutable baseline catalog and the canonical L5
measurement registry every time an entry is used.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

import duckdb
import pandas as pd
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon, contracts
from polisyos.fabric import connectors as fabric_connectors
from polisyos.fabric import data_plane as fabric_data_plane

from .overlay import (
    AcquisitionDatasetRegistration,
    MetricFieldBinding,
    build_metric_field_binding,
)
from .variable_alignment import score_variable_pair

ArtifactID = artifacts.ArtifactID
ArtifactStore = artifacts.ArtifactStore
DataSnapshot = contracts.DataSnapshot
DataSnapshotRef = contracts.DataSnapshotRef
EvidenceBundle = contracts.EvidenceBundle
EvidenceBundleRef = contracts.EvidenceBundleRef
FetchResult = fabric_connectors.FetchResult
JournalEventRef = fabric_data_plane.JournalEventRef
LiveExecutionAuthorization = fabric_data_plane.LiveExecutionAuthorization
ResultSerializer = fabric_connectors.ResultSerializer
SourceProfileRegistry = fabric_connectors.SourceProfileRegistry
canonical_json_bytes = fabric_data_plane.canonical_json_bytes
from_canonical_bytes = canon.from_canonical_bytes

ACQUISITION_AUTHORITY_SCHEMA_VERSION = "polisyos.data_forge.acquisition_authority.v1"
ACQUISITION_AUTHORITY_PROVISION_SCHEMA_VERSION = (
    "polisyos.data_forge.acquisition_authority_provision.v1"
)
LIVE_SOURCE_EXECUTION_EVIDENCE_SCHEMA_VERSION = (
    "polisyos.data_forge.live_source_execution_evidence.v1"
)
LOCAL_SOURCE_RIGHTS_RECEIPT_SCHEMA_VERSION = "polisyos.data_forge.local_source_rights_receipt.v1"
LOCAL_SOURCE_RIGHTS_DECLARATION_SCHEMA_VERSION = (
    "polisyos.data_forge.local_source_rights_declaration.v1"
)
LOCAL_RIGHTS_TRUST_REGISTRY_SCHEMA_VERSION = "polisyos.data_forge.local_rights_trust_registry.v1"
DEFAULT_ACQUISITION_AUTHORITY_REGISTRY = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_registry.json"
)
DEFAULT_ACQUISITION_AUTHORITY_PROVISION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_provision.json"
)
DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY = Path(
    "architecture/policy_design_case/layer3_gy_n13b_local_rights_trust.json"
)
DEFAULT_L5_MEASUREMENT_REGISTRY = Path(
    "production_data/canonical/local_data_20260501/"
    "ukraine_server_support_20260410/runtime_calibration_internals/"
    "calibration/d2/measurement_registry.json"
)
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_PROVISION_CONSTRUCTION_TOKEN = object()


class AcquisitionAuthorityError(RuntimeError):
    """Fail-closed canonical authority resolution error."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail or code}")


class LicenseDisposition(StrEnum):
    """Disposition recomputed from a narrow known-license policy."""

    ADMISSIBLE_OPEN = "admissible_open"
    UNCLEAR = "unclear"
    RESTRICTED = "restricted"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthoritySchemaColumn(_StrictModel):
    """One declared normalized response field carried on the request."""

    name: str = Field(min_length=1)
    logical_types: tuple[str, ...] = Field(min_length=1)
    nullable: bool

    @model_validator(mode="after")
    def _types_are_normalized(self) -> Self:
        if self.logical_types != tuple(sorted(set(self.logical_types))):
            raise ValueError("schema logical types must be unique and sorted")
        return self


class LocalRightsTrustedAuthority(_StrictModel):
    """One signature trust root for independently owned local-source rights."""

    authority_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    rights_authority: str = Field(min_length=1)
    authority_ref: str = Field(pattern=r"^https://[^\s]+$")
    ed25519_public_key_base64: str = Field(min_length=1)
    admissible_license_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _trust_root_is_decisive(self) -> Self:
        if self.admissible_license_ids != tuple(sorted(set(self.admissible_license_ids))):
            raise ValueError("trusted license ids must be unique and sorted")
        try:
            key = base64.b64decode(self.ed25519_public_key_base64, validate=True)
            Ed25519PublicKey.from_public_bytes(key)
        except Exception as exc:
            raise ValueError("trusted Ed25519 public key is invalid") from exc
        return self


class LocalRightsTrustRegistry(_StrictModel):
    """Content-derived trust roots used only for signed local rights evidence."""

    schema_version: Literal["polisyos.data_forge.local_rights_trust_registry.v1"] = (
        LOCAL_RIGHTS_TRUST_REGISTRY_SCHEMA_VERSION
    )
    authorities: tuple[LocalRightsTrustedAuthority, ...]
    content_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _registry_is_recomputed(self) -> Self:
        ids = tuple(authority.authority_id for authority in self.authorities)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("local rights trust roots must be unique and sorted")
        expected = fabric_data_plane.content_sha256(
            {
                "schema_version": self.schema_version,
                "authorities": [
                    authority.model_dump(mode="json") for authority in self.authorities
                ],
            }
        )
        if self.content_sha256 != expected:
            raise ValueError("local rights trust registry identity must be recomputed")
        return self


class LiveHarnessReceiptProvisionEntry(_StrictModel):
    """One canonical E7 receipt owner bound to an entry and live attempt."""

    entry_id: str = Field(pattern=r"^acquisition-authority:sha256:[0-9a-f]{64}$")
    attempt_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]+$")
    receipt_owner_ref: str = Field(pattern=r"^repo://[^\s]+$")
    receipt_content_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _owner_ref_is_repo_relative(self) -> Self:
        relative = Path(self.receipt_owner_ref.removeprefix("repo://"))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("live harness receipt owner ref must be repo-relative")
        return self

    def relative_path(self) -> Path:
        """Return the validated repository-relative owner path."""

        return Path(self.receipt_owner_ref.removeprefix("repo://"))


class AcquisitionAuthorityProvision(_StrictModel):
    """Separately produced trust anchor for acquisition authority resolution."""

    schema_version: Literal["polisyos.data_forge.acquisition_authority_provision.v1"] = (
        ACQUISITION_AUTHORITY_PROVISION_SCHEMA_VERSION
    )
    provision_id: str = Field(pattern=r"^acquisition-authority-provision:sha256:[0-9a-f]{64}$")
    baseline_owner_ref: str = Field(pattern=r"^(repo|provision)://[^\s]+$")
    baseline_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    l5_measurement_registry_owner_ref: str = Field(pattern=r"^(repo|provision)://[^\s]+$")
    l5_measurement_registry_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    local_rights_trust_anchor_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    live_harness_receipts: tuple[LiveHarnessReceiptProvisionEntry, ...] = ()
    authority_purpose: Literal[
        "resolve_baseline_and_local_rights_trust_only",
        "resolve_acquisition_owners_and_live_harness_receipts",
    ] = "resolve_baseline_and_local_rights_trust_only"
    may_not_use_for: tuple[Literal["acquisition_registry_self_authorization"]] = (
        "acquisition_registry_self_authorization",
    )

    @model_validator(mode="after")
    def _identity_is_recomputed(self) -> Self:
        receipt_keys = tuple(
            (entry.entry_id, entry.attempt_id) for entry in self.live_harness_receipts
        )
        if receipt_keys != tuple(sorted(set(receipt_keys))):
            raise ValueError("live harness receipt provisions must be unique and sorted")
        expected_purpose = (
            "resolve_acquisition_owners_and_live_harness_receipts"
            if self.live_harness_receipts
            else "resolve_baseline_and_local_rights_trust_only"
        )
        if self.authority_purpose != expected_purpose:
            raise ValueError("acquisition authority purpose must derive from owners")
        expected = "acquisition-authority-provision:" + (
            fabric_data_plane.content_sha256(self.identity_payload())
        )
        if self.provision_id != expected:
            raise ValueError("acquisition authority provision identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the trust projection defining this provision receipt."""

        payload = {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "provision_id"
        }
        # Preserve the identity of pre-E7/local-only fixture provisions.  The
        # empty default authorizes no live execution and therefore contributes
        # no authority-bearing content.
        if not self.live_harness_receipts:
            payload.pop("live_harness_receipts")
        return payload


class LocalSourceRightsDeclaration(_StrictModel):
    """Owner-supplied, content-derived declaration for one local source."""

    schema_version: Literal["polisyos.data_forge.local_source_rights_declaration.v1"] = (
        LOCAL_SOURCE_RIGHTS_DECLARATION_SCHEMA_VERSION
    )
    declaration_id: str = Field(pattern=r"^local-rights-declaration:sha256:[0-9a-f]{64}$")
    source_path: str = Field(min_length=1)
    source_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    license_id: str = Field(min_length=1)
    authority_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    rights_authority: str = Field(min_length=1)
    authority_ref: str = Field(pattern=r"^https://[^\s]+$")
    signature_base64: str = Field(min_length=1)

    @model_validator(mode="after")
    def _identity_and_path_are_recomputed(self) -> Self:
        path = Path(self.source_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("local rights declaration path must be repo-relative")
        try:
            signature = base64.b64decode(self.signature_base64, validate=True)
        except Exception as exc:
            raise ValueError("local rights declaration signature is invalid") from exc
        if len(signature) != 64:
            raise ValueError("local rights declaration signature is invalid")
        expected = "local-rights-declaration:" + fabric_data_plane.content_sha256(
            self.identity_payload()
        )
        if self.declaration_id != expected:
            raise ValueError("local rights declaration identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the projection defining this owner declaration."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "declaration_id"
        }

    def signed_payload(self) -> dict[str, object]:
        """Return exact bytes that the owner signature must cover."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key not in {"declaration_id", "signature_base64"}
        }


class LocalSourceRightsReceipt(_StrictModel):
    """Verifier-produced evidence binding a source to an owner declaration."""

    schema_version: Literal["polisyos.data_forge.local_source_rights_receipt.v1"] = (
        LOCAL_SOURCE_RIGHTS_RECEIPT_SCHEMA_VERSION
    )
    receipt_id: str = Field(pattern=r"^local-rights:sha256:[0-9a-f]{64}$")
    source_path: str = Field(min_length=1)
    source_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    license_id: str = Field(min_length=1)
    authority_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    rights_authority: str = Field(min_length=1)
    authority_ref: str = Field(pattern=r"^https://[^\s]+$")
    rights_document_path: str = Field(min_length=1)
    rights_document_sha256: str = Field(pattern=_SHA256_PATTERN)
    rights_declaration_id: str = Field(pattern=r"^local-rights-declaration:sha256:[0-9a-f]{64}$")
    trust_registry_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    verifier_ref: Literal["polisyos.data_forge.verify_local_source_rights/v1"] = (
        "polisyos.data_forge.verify_local_source_rights/v1"
    )
    verification_method: Literal["content_bound_owner_document"] = "content_bound_owner_document"

    @model_validator(mode="after")
    def _identity_and_paths_are_recomputed(self) -> Self:
        for value in (self.source_path, self.rights_document_path):
            path = Path(value)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("local rights receipt paths must be repo-relative")
        expected = "local-rights:" + fabric_data_plane.content_sha256(self.identity_payload())
        if self.receipt_id != expected:
            raise ValueError("local rights receipt identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the projection defining this rights receipt."""

        return {
            key: value for key, value in self.model_dump(mode="json").items() if key != "receipt_id"
        }


class AcquisitionAuthorityEntry(_StrictModel):
    """Registry-owned last-mile edge whose upstream facts remain owner-resolved."""

    entry_id: str = Field(pattern=r"^acquisition-authority:sha256:[0-9a-f]{64}$")
    source_lane: Literal["local_lift", "live_fetch"]
    target_variable: str = Field(min_length=1)
    landing_dataset_id: str = Field(min_length=1)
    landing_distribution_id: str = Field(min_length=1)
    source_catalog_dataset_id: str | None = None
    source_catalog_distribution_id: str | None = None
    upstream_metric_id: str | None = None
    catalog_raw_variable: str | None = None
    raw_field: str = Field(min_length=1)
    raw_unit: str = Field(min_length=1)
    canonical_unit: str = Field(min_length=1)
    unit_transform: str = Field(min_length=1)
    unit_transform_ref: str = Field(min_length=1)
    alignment_method: Literal["exact", "semantic", "meta_analytic"]
    alignment_confidence: float = Field(ge=0.0, le=1.0)
    is_proxy: bool
    proxy_penalty: float = Field(ge=0.0, le=1.0)
    aggregation_method: Literal["identity", "mean", "sum", "last"]
    valid_min: float | None = None
    valid_max: float | None = None
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    schema_contract_ref: str = Field(min_length=1)
    schema_columns: tuple[AuthoritySchemaColumn, ...] = Field(min_length=1)
    l5_family_id: str = Field(min_length=1)
    local_source_path: str | None = None
    local_source_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    local_license_id: str | None = None
    local_rights_receipt_path: str | None = None
    local_rights_receipt_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    country_codes: tuple[str, ...] = Field(min_length=1)
    temporal_start: str | None = None
    temporal_end: str | None = None

    @model_validator(mode="after")
    def _entry_is_narrow_and_content_bound(self) -> Self:
        names = tuple(column.name for column in self.schema_columns)
        if names != tuple(sorted(set(names))):
            raise ValueError("authority schema columns must be unique and sorted")
        if self.raw_field not in names:
            raise ValueError("authority raw field must travel in the schema contract")
        if self.alignment_method == "exact" and (
            self.raw_field != self.target_variable or abs(self.alignment_confidence - 1.0) > 1e-9
        ):
            raise ValueError("exact authority alignment requires an identical variable")
        if any(ref.startswith(("self://", "inline://")) for ref in self.evidence_refs):
            raise ValueError("authority evidence cannot be self-authored")
        if not self.unit_transform_ref.startswith(("repo://", "fabric://")):
            raise ValueError("unit transform requires a resolvable owner ref")
        live_fields = (
            self.source_catalog_dataset_id,
            self.source_catalog_distribution_id,
            self.upstream_metric_id,
            self.catalog_raw_variable,
        )
        if self.source_lane == "live_fetch" and not all(live_fields):
            raise ValueError("live authority entry requires its complete catalog edge")
        local_fields = (
            self.local_source_path,
            self.local_source_sha256,
            self.local_license_id,
            self.local_rights_receipt_path,
            self.local_rights_receipt_sha256,
        )
        if self.source_lane == "live_fetch" and any(local_fields):
            raise ValueError("live authority entry cannot carry local authority fields")
        if self.source_lane == "local_lift" and any(live_fields):
            raise ValueError("local authority entry cannot carry live catalog fields")
        if self.source_lane == "local_lift" and not (all(local_fields)):
            raise ValueError(
                "local authority entry requires independent content-bound rights evidence"
            )
        if self.entry_id != "acquisition-authority:" + fabric_data_plane.content_sha256(
            self.identity_payload()
        ):
            raise ValueError("authority entry identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the narrow projection defining this last-mile entry."""

        return {
            key: value for key, value in self.model_dump(mode="json").items() if key != "entry_id"
        }

    def schema_projection(self) -> dict[str, object]:
        """Return the C1 schema projection that must travel with a request."""

        return {
            "schema_contract_ref": self.schema_contract_ref,
            "columns": [column.model_dump(mode="json") for column in self.schema_columns],
        }


class AcquisitionAuthorityRegistry(_StrictModel):
    """Content-bound registry of all executable acquisition field edges."""

    schema_version: Literal[ACQUISITION_AUTHORITY_SCHEMA_VERSION] = (
        ACQUISITION_AUTHORITY_SCHEMA_VERSION
    )
    baseline_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    l5_measurement_registry_sha256: str = Field(pattern=_SHA256_PATTERN)
    entries: tuple[AcquisitionAuthorityEntry, ...]
    content_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _registry_is_recomputed(self) -> Self:
        ids = tuple(entry.entry_id for entry in self.entries)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("authority entries must be unique and sorted")
        expected = fabric_data_plane.content_sha256(
            {
                "schema_version": self.schema_version,
                "baseline_content_sha256": self.baseline_content_sha256,
                "l5_measurement_registry_sha256": self.l5_measurement_registry_sha256,
                "entries": [entry.model_dump(mode="json") for entry in self.entries],
            }
        )
        if self.content_sha256 != expected:
            raise ValueError("authority registry identity must be recomputed")
        return self


class ResolvedL5Trust(_StrictModel):
    """L5 trust projection recomputed from the canonical measurement registry."""

    family_id: str
    tier: str
    trust_cap: float = Field(ge=0.0, le=1.0)
    trust_multiplier: float = Field(ge=0.0, le=1.0)
    authority_ref: str
    owner_ref: str
    owner_content_sha256: str = Field(pattern=_SHA256_PATTERN)


class _HarnessDryRunOutcome(StrEnum):
    """N13a dry-run outcomes accepted at the runtime evidence boundary."""

    REPLAY_FIXTURE_MISSING = "replay_fixture_missing_after_interception"
    FETCH_RESULT_VALIDATED = "fetch_result_validated"
    FETCH_COMPLETED_WITHOUT_INTERCEPTION = "fetch_completed_without_interception"
    INTERCEPTED_RESPONSE_REJECTED = "intercepted_response_rejected"
    CONNECTOR_OWNER_MISSING = "connector_owner_missing"
    CONNECTOR_PROTOCOL_INVALID = "connector_protocol_invalid"
    SOURCE_PROFILE_MISSING = "source_profile_missing"
    SOURCE_PROFILE_MISMATCH = "source_profile_mismatch"
    PRETRANSPORT_REJECTED = "pretransport_rejected"
    NETWORK_ESCAPE_BLOCKED = "network_escape_blocked"


class _StrictHarnessModel(BaseModel):
    """Exact runtime projection of the frozen N13a receipt contract."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _HarnessDryRunAttempt(_StrictHarnessModel):
    """One actual connector carrier attempt under the E7 simulator fence."""

    attempt_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    source_profile_family: str | None = None
    request_dataset_id: str = Field(min_length=1)
    fetch_request_key: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    connection_config_content_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    connector_fetch_invoked: bool
    fetch_completed: bool
    outcome: _HarnessDryRunOutcome
    finding_code: str | None = None
    failure_type: str | None = None
    simulator_mode: Literal["replay"]
    simulator_call_count: int = Field(ge=0)
    transport_intercepted: bool
    network_escape_attempt_count: int = Field(ge=0)
    actual_network_call_count: Literal[0]

    @model_validator(mode="after")
    def _outcome_is_recomputed(self) -> Self:
        reached_simulator = self.simulator_call_count > 0
        if self.transport_intercepted != reached_simulator:
            raise ValueError("transport interception must derive from simulator calls")
        if self.outcome in {
            _HarnessDryRunOutcome.REPLAY_FIXTURE_MISSING,
            _HarnessDryRunOutcome.FETCH_RESULT_VALIDATED,
            _HarnessDryRunOutcome.INTERCEPTED_RESPONSE_REJECTED,
        }:
            if not self.connector_fetch_invoked or not reached_simulator:
                raise ValueError("simulator outcomes require an intercepted fetch")
        elif reached_simulator:
            raise ValueError("pretransport outcomes cannot claim simulator calls")
        completed = self.outcome in {
            _HarnessDryRunOutcome.FETCH_RESULT_VALIDATED,
            _HarnessDryRunOutcome.FETCH_COMPLETED_WITHOUT_INTERCEPTION,
        }
        if self.fetch_completed != completed:
            raise ValueError("fetch completion must derive from dry-run outcome")
        if self.outcome is _HarnessDryRunOutcome.NETWORK_ESCAPE_BLOCKED:
            if self.network_escape_attempt_count < 1:
                raise ValueError("network escape outcome requires an escape attempt")
        elif self.network_escape_attempt_count:
            raise ValueError("escape attempts require the matching typed outcome")
        if (self.failure_type is not None) != (not self.fetch_completed):
            raise ValueError("failure type must derive from dry-run outcome")
        if (self.finding_code is not None) != (
            self.outcome is not _HarnessDryRunOutcome.FETCH_RESULT_VALIDATED
        ):
            raise ValueError("finding code must derive from dry-run outcome")
        request_built = self.fetch_request_key is not None
        config_built = self.connection_config_content_sha256 is not None
        if request_built != config_built:
            raise ValueError("request and connection-config evidence must co-resolve")
        if self.connector_fetch_invoked and not request_built:
            raise ValueError("invoked connector requires request and config evidence")
        return self


_REQUIRED_HARNESS_CHECKS = frozenset(
    {
        "capability_gated_methods_present",
        "connect_returns_unique_sessions",
        "core_methods_are_async",
        "disconnect_idempotent",
        "protocol_compliance",
        "required_class_attributes",
    }
)


class _HarnessFamilyReceipt(_StrictHarnessModel):
    """Full N13a connector-family receipt revalidated at live authorization."""

    connector_id: str = Field(min_length=1)
    component_id: str | None = None
    connector_class: str | None = None
    protocol_violations: tuple[str, ...]
    protocol_conformant: bool
    harness_checks_passed: tuple[str, ...]
    harness_check_failures: tuple[str, ...]
    carrier_denominator: int = Field(ge=1)
    carrier_attempt_count: int = Field(ge=1)
    dry_run_attempts: tuple[_HarnessDryRunAttempt, ...]
    outcome_counts: dict[_HarnessDryRunOutcome, int]
    safe_dry_run_passed: bool
    simulator_mode: Literal["replay"]
    simulator_intercepted: bool
    simulator_call_count: int = Field(ge=0)
    network_escape_attempt_count: int = Field(ge=0)
    simulator_network_calls: Literal[0]

    @model_validator(mode="after")
    def _status_is_recomputed(self) -> Self:
        owner_resolved = self.component_id is not None and self.connector_class is not None
        if (self.component_id is None) != (self.connector_class is None):
            raise ValueError("component id and connector class must co-resolve")
        expected_protocol = owner_resolved and not self.protocol_violations
        if self.protocol_conformant != expected_protocol:
            raise ValueError("protocol status must derive from owner validation")
        passed = self.harness_checks_passed
        failures = self.harness_check_failures
        if passed != tuple(sorted(set(passed))):
            raise ValueError("passed harness checks must be unique and sorted")
        if failures != tuple(sorted(set(failures))):
            raise ValueError("failed harness checks must be unique and sorted")
        if set(passed) & set(failures):
            raise ValueError("harness checks cannot both pass and fail")
        if owner_resolved and set(passed) | set(failures) != _REQUIRED_HARNESS_CHECKS:
            raise ValueError("every public harness check requires a typed result")
        if not owner_resolved and (passed or failures):
            raise ValueError("missing owners cannot claim harness execution")
        attempt_ids = tuple(item.attempt_id for item in self.dry_run_attempts)
        if attempt_ids != tuple(sorted(set(attempt_ids))):
            raise ValueError("dry-run attempts must be unique and sorted")
        if self.carrier_attempt_count != len(self.dry_run_attempts):
            raise ValueError("carrier count must equal nested dry-run attempts")
        if self.carrier_denominator != self.carrier_attempt_count:
            raise ValueError("every selected carrier requires a dry-run attempt")
        expected_outcomes = dict(
            sorted(
                Counter(item.outcome for item in self.dry_run_attempts).items(),
                key=lambda item: item[0],
            )
        )
        if self.outcome_counts != expected_outcomes:
            raise ValueError("outcome counts must derive from dry-run attempts")
        simulator_calls = sum(item.simulator_call_count for item in self.dry_run_attempts)
        if self.simulator_call_count != simulator_calls:
            raise ValueError("family simulator calls must sum carrier attempts")
        escape_attempts = sum(item.network_escape_attempt_count for item in self.dry_run_attempts)
        if self.network_escape_attempt_count != escape_attempts:
            raise ValueError("family escape attempts must sum carrier attempts")
        if self.simulator_intercepted != (simulator_calls > 0):
            raise ValueError("family interception must derive from simulator calls")
        safe_outcome = any(
            item.outcome
            in {
                _HarnessDryRunOutcome.REPLAY_FIXTURE_MISSING,
                _HarnessDryRunOutcome.FETCH_RESULT_VALIDATED,
            }
            for item in self.dry_run_attempts
        )
        expected_safe = (
            expected_protocol
            and not failures
            and set(passed) == _REQUIRED_HARNESS_CHECKS
            and safe_outcome
            and self.simulator_intercepted
            and self.network_escape_attempt_count == 0
        )
        if self.safe_dry_run_passed != expected_safe:
            raise ValueError("safe dry-run status must derive from harness evidence")
        return self


class ResolvedLiveHarnessReceipt(_StrictModel):
    """Canonical E7 family receipt and selected carrier owner projection."""

    entry_id: str = Field(pattern=r"^acquisition-authority:sha256:[0-9a-f]{64}$")
    attempt_id: str = Field(min_length=1)
    receipt_owner_ref: str = Field(pattern=r"^repo://[^\s]+$")
    receipt_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    family_receipt: dict[str, Any]
    family_receipt_sha256: str = Field(pattern=_SHA256_PATTERN)
    carrier_receipt_sha256: str = Field(pattern=_SHA256_PATTERN)
    source_profile_family: str = Field(min_length=1)
    connection_config_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    fetch_request_key: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _content_identity_is_recomputed(self) -> Self:
        if self.family_receipt_sha256 != fabric_data_plane.content_sha256(self.family_receipt):
            raise ValueError("live harness family identity must be recomputed")
        return self


class ResolvedAcquisitionAuthority(_StrictModel):
    """Independent owner result consumed by passport and overlay admission."""

    entry: AcquisitionAuthorityEntry
    authority_provision_id: str = Field(
        pattern=r"^acquisition-authority-provision:sha256:[0-9a-f]{64}$"
    )
    authority_provision_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    registry_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    baseline_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    field_binding: MetricFieldBinding
    registration: AcquisitionDatasetRegistration
    license_id: str
    license_disposition: LicenseDisposition
    license_authority_ref: str = Field(min_length=1)
    license_authority_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    l5_trust: ResolvedL5Trust
    upstream_catalog_projection_sha256: str = Field(pattern=_SHA256_PATTERN)
    effective_authority_score: float = Field(ge=0.0, le=1.0)


class LiveSourceExecutionEvidence(_StrictModel):
    """Content-derived proof binding raw HTTP and normalized Fabric carriers."""

    schema_version: Literal["polisyos.data_forge.live_source_execution_evidence.v1"] = (
        LIVE_SOURCE_EXECUTION_EVIDENCE_SCHEMA_VERSION
    )
    authorization: LiveExecutionAuthorization
    family_receipt: dict[str, Any]
    family_receipt_sha256: str = Field(pattern=_SHA256_PATTERN)
    request_ref: JournalEventRef
    raw_evidence_ref: JournalEventRef
    transport_trace: fabric_data_plane.LiveTransportTrace
    raw_artifact_id: ArtifactID
    evidence_bundle_ref: EvidenceBundleRef
    data_snapshot_ref: DataSnapshotRef
    normalized_data_artifact_id: ArtifactID
    call_count: Literal[1]
    variable_count: Literal[1]
    page_count: Literal[1]
    baseline_before_sha256: str = Field(pattern=_SHA256_PATTERN)
    baseline_after_sha256: str = Field(pattern=_SHA256_PATTERN)
    raw_body_sha256: str = Field(pattern=_SHA256_PATTERN)
    normalized_result_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    content_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _identity_and_decisive_links_are_recomputed(self) -> Self:
        receipt_hash = fabric_data_plane.content_sha256(self.family_receipt)
        if (
            self.family_receipt_sha256 != receipt_hash
            or self.authorization.harness.family_receipt_sha256 != receipt_hash
        ):
            raise ValueError("live execution family receipt identity must be recomputed")
        if self.request_ref.event_kind != "request":
            raise ValueError("live execution request ref must address a request event")
        if self.raw_evidence_ref.event_kind != "raw_response":
            raise ValueError("live execution raw ref must address a raw-response event")
        if (
            self.request_ref.journal_path != self.raw_evidence_ref.journal_path
            or self.request_ref.sequence >= self.raw_evidence_ref.sequence
        ):
            raise ValueError("live execution journal refs must form one ordered carrier")
        if (
            self.transport_trace.request_ref != self.request_ref
            or self.transport_trace.raw_evidence_ref != self.raw_evidence_ref
            or self.transport_trace.attempt_id != self.authorization.attempt_id
            or self.transport_trace.connector_id != self.authorization.connector_id
            or self.call_count != self.transport_trace.call_count
        ):
            raise ValueError("live execution transport trace must bind the carrier")
        if (
            self.baseline_before_sha256 != self.baseline_after_sha256
            or self.baseline_before_sha256 != self.authorization.baseline_sha256
        ):
            raise ValueError("live execution baseline must remain immutable")
        if self.raw_body_sha256 != self.normalized_result_content_sha256:
            raise ValueError("normalized result must version the exact raw HTTP body")
        if self.content_sha256 != fabric_data_plane.content_sha256(self.identity_payload()):
            raise ValueError("live execution evidence identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return every decisive field except the derived evidence identity."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "content_sha256"
        }


def build_live_source_execution_evidence(
    *,
    authorization: LiveExecutionAuthorization,
    family_receipt: Mapping[str, Any],
    request_ref: JournalEventRef,
    raw_evidence_ref: JournalEventRef,
    transport_trace: fabric_data_plane.LiveTransportTrace,
    raw_artifact_id: str | ArtifactID,
    evidence_bundle_ref: EvidenceBundleRef,
    data_snapshot_ref: DataSnapshotRef,
    normalized_data_artifact_id: str | ArtifactID,
    variable_count: int,
    page_count: int,
    baseline_before_sha256: str,
    baseline_after_sha256: str,
    raw_body_sha256: str,
    normalized_result_content_sha256: str,
) -> LiveSourceExecutionEvidence:
    """Build strict dual-carrier evidence without accepting a caller-pinned identity."""

    values = {
        "authorization": authorization,
        "family_receipt": dict(family_receipt),
        "family_receipt_sha256": fabric_data_plane.content_sha256(family_receipt),
        "request_ref": request_ref,
        "raw_evidence_ref": raw_evidence_ref,
        "transport_trace": transport_trace,
        "raw_artifact_id": ArtifactID.model_validate(raw_artifact_id),
        "evidence_bundle_ref": evidence_bundle_ref,
        "data_snapshot_ref": data_snapshot_ref,
        "normalized_data_artifact_id": ArtifactID.model_validate(normalized_data_artifact_id),
        "call_count": transport_trace.call_count,
        "variable_count": variable_count,
        "page_count": page_count,
        "baseline_before_sha256": baseline_before_sha256,
        "baseline_after_sha256": baseline_after_sha256,
        "raw_body_sha256": raw_body_sha256,
        "normalized_result_content_sha256": normalized_result_content_sha256,
    }
    provisional = LiveSourceExecutionEvidence.model_construct(
        **values,
        content_sha256="sha256:" + "0" * 64,
    )
    return LiveSourceExecutionEvidence(
        **values,
        content_sha256=fabric_data_plane.content_sha256(provisional.identity_payload()),
    )


def build_authority_entry(**values: object) -> AcquisitionAuthorityEntry:
    """Build one content-bound authority entry without accepting a pinned id."""

    provisional = AcquisitionAuthorityEntry.model_construct(
        entry_id="acquisition-authority:sha256:" + "0" * 64,
        **values,
    )
    identity = provisional.identity_payload()
    return AcquisitionAuthorityEntry(
        entry_id="acquisition-authority:" + fabric_data_plane.content_sha256(identity),
        **values,
    )


def build_acquisition_authority_provision(
    **values: object,
) -> AcquisitionAuthorityProvision:
    """Build the separately persisted resolver provision without a pinned id."""

    normalized = dict(values)
    receipt_values = normalized.get("live_harness_receipts")
    if receipt_values is not None:
        if not isinstance(receipt_values, Sequence) or isinstance(
            receipt_values,
            (str, bytes, bytearray),
        ):
            raise ValueError("live harness receipt provisions must be a sequence")
        normalized["live_harness_receipts"] = tuple(
            LiveHarnessReceiptProvisionEntry.model_validate(item) for item in receipt_values
        )
        if normalized["live_harness_receipts"]:
            normalized.setdefault(
                "authority_purpose",
                "resolve_acquisition_owners_and_live_harness_receipts",
            )
    provisional = AcquisitionAuthorityProvision.model_construct(
        provision_id="acquisition-authority-provision:sha256:" + "0" * 64,
        **normalized,
    )
    return AcquisitionAuthorityProvision(
        provision_id=(
            "acquisition-authority-provision:"
            + fabric_data_plane.content_sha256(provisional.identity_payload())
        ),
        **normalized,
    )


def build_local_source_rights_declaration(
    **values: object,
) -> LocalSourceRightsDeclaration:
    """Format an owner declaration; authority is earned only when it is resolved."""

    provisional = LocalSourceRightsDeclaration.model_construct(
        declaration_id="local-rights-declaration:sha256:" + "0" * 64,
        **values,
    )
    return LocalSourceRightsDeclaration(
        declaration_id=(
            "local-rights-declaration:"
            + fabric_data_plane.content_sha256(provisional.identity_payload())
        ),
        **values,
    )


def build_local_rights_trust_registry(
    *,
    authorities: tuple[LocalRightsTrustedAuthority, ...],
) -> LocalRightsTrustRegistry:
    """Build a byte-stable registry from separately provisioned public keys."""

    ordered = tuple(sorted(authorities, key=lambda item: item.authority_id))
    projection = {
        "schema_version": LOCAL_RIGHTS_TRUST_REGISTRY_SCHEMA_VERSION,
        "authorities": [item.model_dump(mode="json") for item in ordered],
    }
    return LocalRightsTrustRegistry(
        authorities=ordered,
        content_sha256=fabric_data_plane.content_sha256(projection),
    )


def verify_local_source_rights(
    *,
    repo_root: Path,
    source_path: str,
    rights_document_path: str,
    trust_registry_path: str = DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY.as_posix(),
) -> LocalSourceRightsReceipt:
    """Reopen source and owner declaration bytes and derive a verifier receipt."""

    root = Path(repo_root).resolve()
    source_relative = _safe_repo_relative_path(source_path, code="local_source_path")
    document_relative = _safe_repo_relative_path(
        rights_document_path,
        code="local_rights_document_path",
    )
    trust_relative = _safe_repo_relative_path(
        trust_registry_path,
        code="local_rights_trust_registry_path",
    )
    receipt, _, _ = _derive_local_source_rights_receipt(
        root=root,
        source_relative=source_relative,
        document_relative=document_relative,
        trust_relative=trust_relative,
        expected_trust_file_sha256=None,
    )
    return receipt


def build_authority_registry(
    *,
    baseline_content_sha256: str,
    l5_measurement_registry_sha256: str,
    entries: tuple[AcquisitionAuthorityEntry, ...],
) -> AcquisitionAuthorityRegistry:
    """Build a byte-stable registry model from sorted entries."""

    ordered = tuple(sorted(entries, key=lambda entry: entry.entry_id))
    projection = {
        "schema_version": ACQUISITION_AUTHORITY_SCHEMA_VERSION,
        "baseline_content_sha256": baseline_content_sha256,
        "l5_measurement_registry_sha256": l5_measurement_registry_sha256,
        "entries": [entry.model_dump(mode="json") for entry in ordered],
    }
    return AcquisitionAuthorityRegistry(
        baseline_content_sha256=baseline_content_sha256,
        l5_measurement_registry_sha256=l5_measurement_registry_sha256,
        entries=ordered,
        content_sha256=fabric_data_plane.content_sha256(projection),
    )


class CanonicalAcquisitionAuthority:
    """Resolver that reopens every decisive owner instead of trusting callers."""

    def __init__(
        self,
        *,
        repo_root: Path,
        baseline_path: Path,
        l5_measurement_registry_path: Path,
        provision: AcquisitionAuthorityProvision,
        provision_content_sha256: str,
        _construction_token: object,
    ) -> None:
        if _construction_token is not _PROVISION_CONSTRUCTION_TOKEN:
            raise TypeError("use CanonicalAcquisitionAuthority.from_provision")
        self.repo_root = Path(repo_root).resolve()
        self.baseline_path = Path(baseline_path).resolve()
        self.l5_path = Path(l5_measurement_registry_path).resolve()
        self.provision = provision
        self.provision_content_sha256 = provision_content_sha256
        self.baseline_owner_ref = provision.baseline_owner_ref
        self.l5_owner_ref = provision.l5_measurement_registry_owner_ref
        self.local_rights_trust_anchor_sha256 = provision.local_rights_trust_anchor_sha256
        self.registry_path = self.repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
        self.local_rights_trust_path = self.repo_root / DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY

    @classmethod
    def from_provision(
        cls,
        *,
        repo_root: Path,
        baseline_path: Path,
        l5_measurement_registry_path: Path | None = None,
    ) -> CanonicalAcquisitionAuthority:
        """Load the canonical provision receipt; callers cannot choose its anchors."""

        root = Path(repo_root).resolve()
        provision, provision_content_sha256 = _load_authority_provision(
            root / DEFAULT_ACQUISITION_AUTHORITY_PROVISION
        )
        baseline = Path(baseline_path).resolve()
        if _file_sha256(baseline) != provision.baseline_content_sha256:
            raise AcquisitionAuthorityError("provision_baseline_identity_drift")
        l5_path = (
            Path(l5_measurement_registry_path).resolve()
            if l5_measurement_registry_path is not None
            else (root / DEFAULT_L5_MEASUREMENT_REGISTRY).resolve()
        )
        if _file_sha256(l5_path) != (provision.l5_measurement_registry_content_sha256):
            raise AcquisitionAuthorityError("provision_l5_identity_drift")
        return cls(
            repo_root=root,
            baseline_path=baseline,
            l5_measurement_registry_path=l5_path,
            provision=provision,
            provision_content_sha256=provision_content_sha256,
            _construction_token=_PROVISION_CONSTRUCTION_TOKEN,
        )

    def resolve(self, entry_id: str) -> ResolvedAcquisitionAuthority:
        """Resolve one entry against fresh registry, catalog, license, and L5 bytes."""

        self._require_provision_unchanged()
        registry = self._load_registry()
        matches = [entry for entry in registry.entries if entry.entry_id == entry_id]
        if len(matches) != 1:
            raise AcquisitionAuthorityError("authority_entry_unresolved", entry_id)
        entry = matches[0]
        if entry.source_lane == "live_fetch":
            (
                projection,
                license_id,
                license_authority_ref,
                license_authority_sha256,
                registration,
            ) = self._resolve_live_catalog(entry)
        else:
            (
                projection,
                license_id,
                license_authority_ref,
                license_authority_sha256,
                registration,
            ) = self._resolve_local_source(
                entry,
                expected_trust_registry_sha256=(self.local_rights_trust_anchor_sha256),
            )
        self._require_landing_identifiers_new(entry)
        disposition = derive_license_disposition(license_id)
        if disposition is not LicenseDisposition.ADMISSIBLE_OPEN:
            raise AcquisitionAuthorityError("license_not_admissible", license_id)
        l5 = self._resolve_l5(
            entry.l5_family_id,
            expected_content_sha256=registry.l5_measurement_registry_sha256,
        )
        binding = build_metric_field_binding(
            dataset_id=entry.landing_dataset_id,
            distribution_id=entry.landing_distribution_id,
            raw_field=entry.raw_field,
            canonical_variable=entry.target_variable,
            raw_unit=entry.raw_unit,
            canonical_unit=entry.canonical_unit,
            unit_transform=entry.unit_transform,
            unit_transform_ref=entry.unit_transform_ref,
            alignment_method=entry.alignment_method,
            alignment_confidence=entry.alignment_confidence,
            is_proxy=entry.is_proxy,
            proxy_penalty=entry.proxy_penalty,
            evidence_refs=entry.evidence_refs,
            aggregation_method=entry.aggregation_method,
            valid_min=entry.valid_min,
            valid_max=entry.valid_max,
        )
        registration = registration.model_copy(update={"field_binding": binding})
        proxy_factor = 1.0 - entry.proxy_penalty if entry.is_proxy else 1.0
        score = round(
            min(
                l5.trust_cap,
                binding.calibrated_alignment_confidence * proxy_factor * l5.trust_multiplier,
            ),
            6,
        )
        return ResolvedAcquisitionAuthority(
            entry=entry,
            authority_provision_id=self.provision.provision_id,
            authority_provision_content_sha256=self.provision_content_sha256,
            registry_content_sha256=registry.content_sha256,
            baseline_content_sha256=registry.baseline_content_sha256,
            field_binding=binding,
            registration=registration,
            license_id=license_id,
            license_disposition=disposition,
            license_authority_ref=license_authority_ref,
            license_authority_content_sha256=license_authority_sha256,
            l5_trust=l5,
            upstream_catalog_projection_sha256=fabric_data_plane.content_sha256(projection),
            effective_authority_score=score,
        )

    def _require_provision_unchanged(self) -> None:
        provision, content_sha256 = _load_authority_provision(
            self.repo_root / DEFAULT_ACQUISITION_AUTHORITY_PROVISION
        )
        if provision != self.provision or content_sha256 != self.provision_content_sha256:
            raise AcquisitionAuthorityError("acquisition_authority_provision_drift")
        if _file_sha256(self.baseline_path) != provision.baseline_content_sha256:
            raise AcquisitionAuthorityError("provision_baseline_identity_drift")
        if _file_sha256(self.l5_path) != (provision.l5_measurement_registry_content_sha256):
            raise AcquisitionAuthorityError("provision_l5_identity_drift")

    def _require_landing_identifiers_new(
        self,
        entry: AcquisitionAuthorityEntry,
    ) -> None:
        """Keep acquisition identities disjoint from immutable epoch zero."""

        con = duckdb.connect(str(self.baseline_path), read_only=True)
        try:
            dataset_collision = int(
                con.execute(
                    "SELECT count(*) FROM ds_datasets WHERE id = ?",
                    [entry.landing_dataset_id],
                ).fetchone()[0]
                or 0
            )
            distribution_collision = int(
                con.execute(
                    "SELECT count(*) FROM ds_distributions WHERE id = ?",
                    [entry.landing_distribution_id],
                ).fetchone()[0]
                or 0
            )
        finally:
            con.close()
        if dataset_collision or distribution_collision:
            raise AcquisitionAuthorityError(
                "landing_identifier_collides_with_epoch_zero",
                f"{entry.landing_dataset_id}:{entry.landing_distribution_id}",
            )

    def verify_source_body(self, entry_id: str, body: bytes) -> bool:
        """Verify local carrier bytes directly; live carriers require E7 authorization."""

        resolved = self.resolve(entry_id)
        if resolved.entry.source_lane != "local_lift":
            return False
        source_path = self.repo_root / str(resolved.entry.local_source_path)
        return source_path.read_bytes() == body

    def resolve_live_harness_receipt(
        self,
        entry_id: str,
        attempt_id: str,
    ) -> ResolvedLiveHarnessReceipt:
        """Reopen the provisioned full N13a receipt for one exact live carrier."""

        resolved = self.resolve(entry_id)
        if resolved.entry.source_lane != "live_fetch":
            raise AcquisitionAuthorityError("live_source_lane_required")
        return self._resolve_live_harness_receipt(resolved, attempt_id)

    def _resolve_live_harness_receipt(
        self,
        resolved: ResolvedAcquisitionAuthority,
        attempt_id: str,
    ) -> ResolvedLiveHarnessReceipt:
        provisions = tuple(
            provision
            for provision in self.provision.live_harness_receipts
            if provision.entry_id == resolved.entry.entry_id and provision.attempt_id == attempt_id
        )
        if len(provisions) != 1:
            raise AcquisitionAuthorityError(
                "live_harness_receipt_provision_unresolved",
                f"{resolved.entry.entry_id}:{attempt_id}",
            )
        provision = provisions[0]
        receipt_path = _resolve_repo_file(
            self.repo_root,
            provision.relative_path(),
            code="live_harness_receipt_path",
        )
        if _file_sha256(receipt_path) != provision.receipt_content_sha256:
            raise AcquisitionAuthorityError("live_harness_receipt_content_drift")
        raw = receipt_path.read_bytes()
        try:
            receipt = _HarnessFamilyReceipt.model_validate_json(raw)
            payload_value = json.loads(raw)
            if not isinstance(payload_value, Mapping):
                raise TypeError("family receipt must be a JSON object")
            payload = {str(key): value for key, value in payload_value.items()}
        except Exception as exc:
            raise AcquisitionAuthorityError(
                "live_harness_receipt_invalid",
                type(exc).__name__,
            ) from exc
        carriers = tuple(
            carrier for carrier in receipt.dry_run_attempts if carrier.attempt_id == attempt_id
        )
        if len(carriers) != 1:
            raise AcquisitionAuthorityError("live_harness_receipt_carrier_mismatch")
        carrier = carriers[0]
        if (
            carrier.fetch_request_key is None
            or carrier.connection_config_content_sha256 is None
            or carrier.source_profile_family is None
        ):
            raise AcquisitionAuthorityError("live_harness_receipt_carrier_binding_missing")
        try:
            harness = fabric_data_plane.derive_harness_authorization_evidence(
                payload,
                attempt_id=attempt_id,
            )
        except Exception as exc:
            raise AcquisitionAuthorityError(
                "live_harness_receipt_carrier_invalid",
                type(exc).__name__,
            ) from exc
        registration = resolved.registration
        if (
            not harness.safe_dry_run_passed
            or harness.connector_id != registration.connector_id
            or harness.profile_id != registration.source_profile_id
            or harness.request_dataset_id != registration.request_dataset_id
        ):
            raise AcquisitionAuthorityError("live_harness_receipt_owner_projection_drift")
        return ResolvedLiveHarnessReceipt(
            entry_id=resolved.entry.entry_id,
            attempt_id=attempt_id,
            receipt_owner_ref=provision.receipt_owner_ref,
            receipt_content_sha256=provision.receipt_content_sha256,
            family_receipt=payload,
            family_receipt_sha256=fabric_data_plane.content_sha256(payload),
            carrier_receipt_sha256=harness.carrier_receipt_sha256,
            source_profile_family=carrier.source_profile_family,
            connection_config_content_sha256=(carrier.connection_config_content_sha256),
            fetch_request_key=carrier.fetch_request_key,
        )

    def resolve_live_source_execution(
        self,
        entry_id: str,
        evidence: LiveSourceExecutionEvidence,
        artifact_store: ArtifactStore,
    ) -> FetchResult[Any]:
        """Reopen and verify both carriers of one authorized live execution.

        The raw HTTP response remains the journal/CAS evidence carrier.  The
        normalized ``FetchResult`` is accepted only through the exact
        ``DataSnapshot.data_ref`` produced by Fabric orchestration.  No caller
        supplied rows participate in this decision.
        """

        try:
            proof = LiveSourceExecutionEvidence.model_validate(
                evidence.model_dump(mode="json")
                if isinstance(evidence, LiveSourceExecutionEvidence)
                else evidence
            )
            resolved = self.resolve(entry_id)
            if resolved.entry.source_lane != "live_fetch":
                raise AcquisitionAuthorityError("live_source_lane_required")
            self._verify_live_owner_projection(resolved, proof)
            self._verify_live_journal_carrier(resolved, proof)
            raw_body = fabric_data_plane.resolve_raw_response_body(proof.raw_evidence_ref)
            raw_hash = f"sha256:{hashlib.sha256(raw_body).hexdigest()}"
            if raw_hash != proof.raw_body_sha256:
                raise AcquisitionAuthorityError("live_raw_body_identity_drift")
            raw_cas = self._reopen_artifact(
                artifact_store,
                proof.raw_artifact_id,
                expected_kind="fabric.acquisition.raw_evidence",
            )
            if raw_cas != raw_body:
                raise AcquisitionAuthorityError("live_raw_journal_cas_mismatch")

            evidence_bundle = EvidenceBundle.model_validate(
                from_canonical_bytes(
                    self._reopen_artifact_ref(
                        artifact_store,
                        proof.evidence_bundle_ref,
                        expected_kind="fabric.evidence_bundle",
                    )
                )
            )
            snapshot = DataSnapshot.model_validate(
                from_canonical_bytes(
                    self._reopen_artifact_ref(
                        artifact_store,
                        proof.data_snapshot_ref,
                        expected_kind="fabric.data_snapshot",
                    )
                )
            )
            if snapshot.evidence_ref != proof.evidence_bundle_ref:
                raise AcquisitionAuthorityError("live_snapshot_evidence_ref_drift")
            if snapshot.data_ref.artifact_id != proof.normalized_data_artifact_id:
                raise AcquisitionAuthorityError("live_snapshot_data_ref_drift")
            if evidence_bundle.sources != [snapshot.data_ref]:
                raise AcquisitionAuthorityError("live_evidence_bundle_source_drift")
            if snapshot.stats.get("datasets_fetched") != 1:
                raise AcquisitionAuthorityError("live_snapshot_dataset_count_invalid")

            normalized_bytes = self._reopen_artifact_ref(
                artifact_store,
                snapshot.data_ref,
            )
            result = ResultSerializer.deserialize(normalized_bytes)
            self._verify_live_normalized_result(resolved, proof, result)
            return result
        except AcquisitionAuthorityError:
            raise
        except Exception as exc:
            raise AcquisitionAuthorityError(
                "live_source_execution_invalid",
                type(exc).__name__,
            ) from exc

    def resolve_live_source_body(
        self,
        entry_id: str,
        evidence: LiveSourceExecutionEvidence,
        artifact_store: ArtifactStore,
    ) -> bytes:
        """Return deterministic normalized rows after full dual-carrier verification."""

        result = self.resolve_live_source_execution(entry_id, evidence, artifact_store)
        return _normalized_fetch_result_body(result)

    def _verify_live_owner_projection(
        self,
        resolved: ResolvedAcquisitionAuthority,
        proof: LiveSourceExecutionEvidence,
    ) -> None:
        actual_baseline = _file_sha256(self.baseline_path)
        if (
            actual_baseline != resolved.baseline_content_sha256
            or actual_baseline != proof.baseline_before_sha256
            or actual_baseline != proof.baseline_after_sha256
            or actual_baseline != proof.authorization.baseline_sha256
        ):
            raise AcquisitionAuthorityError("live_baseline_identity_drift")
        try:
            canonical_receipt = self._resolve_live_harness_receipt(
                resolved,
                proof.authorization.attempt_id,
            )
            if (
                proof.family_receipt != canonical_receipt.family_receipt
                or proof.family_receipt_sha256 != canonical_receipt.family_receipt_sha256
                or proof.authorization.harness.family_receipt_sha256
                != canonical_receipt.family_receipt_sha256
            ):
                raise AcquisitionAuthorityError("live_harness_receipt_evidence_drift")
            profile = SourceProfileRegistry.get_instance().get(
                resolved.registration.source_profile_id
            )
            if profile is None:
                raise AcquisitionAuthorityError("live_source_profile_unresolved")
            if canonical_receipt.source_profile_family != str(profile.connector_family):
                raise AcquisitionAuthorityError("live_harness_profile_family_drift")
            base_config = fabric_connectors.resolve_connection_config(profile)
            if canonical_receipt.connection_config_content_sha256 != (
                fabric_data_plane.content_sha256(base_config.to_dict(redact=True))
            ):
                raise AcquisitionAuthorityError("live_harness_connection_config_drift")
            dry_run_request = fabric_connectors.FetchRequest(
                dataset_id=resolved.registration.request_dataset_id
            )
            if canonical_receipt.fetch_request_key != dry_run_request.request_key:
                raise AcquisitionAuthorityError("live_harness_fetch_request_drift")
            fabric_data_plane.require_authorized_execution(
                proof.authorization,
                family_receipt=canonical_receipt.family_receipt,
            )
        except AcquisitionAuthorityError:
            raise
        except Exception as exc:
            raise AcquisitionAuthorityError(
                "live_harness_authorization_invalid",
                type(exc).__name__,
            ) from exc
        registration = resolved.registration
        authorization = proof.authorization
        if (
            authorization.connector_id != registration.connector_id
            or authorization.profile_id != registration.source_profile_id
            or authorization.request_variables != (registration.request_dataset_id,)
        ):
            raise AcquisitionAuthorityError("live_authorization_catalog_drift")
        profile = SourceProfileRegistry.get_instance().get(registration.source_profile_id)
        if profile is None:
            raise AcquisitionAuthorityError("live_source_profile_unresolved")
        if fabric_data_plane.content_sha256(profile) != authorization.source_profile_sha256:
            raise AcquisitionAuthorityError("live_source_profile_identity_drift")

    def _verify_live_journal_carrier(
        self,
        resolved: ResolvedAcquisitionAuthority,
        proof: LiveSourceExecutionEvidence,
    ) -> None:
        request_event = fabric_data_plane.resolve_journal_event_ref(proof.request_ref)
        raw_event = fabric_data_plane.resolve_journal_event_ref(proof.raw_evidence_ref)
        try:
            transport_trace = fabric_data_plane.resolve_live_transport_trace(proof.raw_evidence_ref)
        except Exception as exc:
            raise AcquisitionAuthorityError(
                "live_transport_trace_invalid",
                type(exc).__name__,
            ) from exc
        if transport_trace != proof.transport_trace:
            raise AcquisitionAuthorityError("live_transport_trace_drift")
        linked_request = fabric_data_plane.resolve_linked_request_event(proof.raw_evidence_ref)
        if linked_request != request_event:
            raise AcquisitionAuthorityError("live_request_raw_link_drift")
        if (
            raw_event.get("attempt_id") != proof.authorization.attempt_id
            or request_event.get("attempt_id") != proof.authorization.attempt_id
        ):
            raise AcquisitionAuthorityError("live_attempt_identity_drift")
        raw_projection = raw_event.get("raw_response")
        if not isinstance(raw_projection, Mapping):
            raise AcquisitionAuthorityError("live_raw_response_missing")
        if raw_projection.get("request_event_sha256") != proof.request_ref.event_sha256:
            raise AcquisitionAuthorityError("live_request_event_ref_drift")
        status_code = raw_projection.get("status_code")
        if (
            isinstance(status_code, bool)
            or not isinstance(status_code, int)
            or not 200 <= status_code < 300
        ):
            raise AcquisitionAuthorityError("live_http_status_not_success")
        request_value = request_event.get("request")
        if not isinstance(request_value, Mapping):
            raise AcquisitionAuthorityError("live_request_missing")
        request = {str(key): value for key, value in request_value.items()}
        if (
            request_event.get("request_sha256") != fabric_data_plane.content_sha256(request)
            or request_event.get("request_sha256") != proof.authorization.request_sha256
        ):
            raise AcquisitionAuthorityError("live_request_identity_drift")
        entry = resolved.entry
        registration = resolved.registration
        expected = {
            "authority_entry_id": entry.entry_id,
            "authority_registry_content_sha256": resolved.registry_content_sha256,
            "variable_id": entry.target_variable,
            "source_lane": "live_fetch",
            "dataset_id": entry.landing_dataset_id,
            "distribution_id": entry.landing_distribution_id,
            "connector_id": registration.connector_id,
            "profile_id": registration.source_profile_id,
            "request_dataset_id": registration.request_dataset_id,
            "request_variables": [registration.request_dataset_id],
            "schema_contract": entry.schema_projection(),
        }
        if any(request.get(key) != value for key, value in expected.items()):
            raise AcquisitionAuthorityError("live_request_owner_projection_drift")
        filters = request.get("filters")
        date_start = request.get("date_start")
        date_end = request.get("date_end")
        page_size = request.get("page_size")
        if (
            not isinstance(filters, Mapping)
            or set(filters) != {"country"}
            or not isinstance(filters.get("country"), Sequence)
            or isinstance(filters.get("country"), (str, bytes, bytearray))
            or len(filters["country"]) != 1
            or str(filters["country"][0]) not in entry.country_codes
            or not isinstance(date_start, str)
            or not isinstance(date_end, str)
            or not _live_date_scope_is_admissible(entry, date_start, date_end)
            or isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or not 0 < page_size <= 20_000
        ):
            raise AcquisitionAuthorityError("live_request_scope_invalid")
        profile = SourceProfileRegistry.get_instance().get(registration.source_profile_id)
        if profile is None:
            raise AcquisitionAuthorityError("live_source_profile_unresolved")
        if registration.connector_id != "worldbank.wdi":
            raise AcquisitionAuthorityError("live_transport_owner_missing")
        country_code = str(filters["country"][0])
        expected_url = (
            profile.base_url.rstrip("/")
            + f"/country/{country_code}/indicator/"
            + registration.request_dataset_id
        )
        expected_params = {
            "date": f"{date_start[:4]}:{date_end[:4]}",
            "format": "json",
            "page": "1",
            "per_page": str(page_size),
        }
        if transport_trace.url != expected_url or transport_trace.params != expected_params:
            raise AcquisitionAuthorityError("live_transport_owner_projection_drift")
        if (
            fabric_data_plane.content_sha256(entry.schema_projection())
            != proof.authorization.schema_contract_sha256
        ):
            raise AcquisitionAuthorityError("live_request_schema_contract_drift")

    def _verify_live_normalized_result(
        self,
        resolved: ResolvedAcquisitionAuthority,
        proof: LiveSourceExecutionEvidence,
        result: FetchResult[Any],
    ) -> None:
        contract = resolved.entry.schema_contract_ref
        if not contract.startswith("fabric://") or "@" not in contract:
            raise AcquisitionAuthorityError("live_schema_contract_ref_invalid")
        schema_id, schema_version = contract.removeprefix("fabric://").rsplit("@", 1)
        if result.schema_id != schema_id or result.schema_version != schema_version:
            raise AcquisitionAuthorityError("live_normalized_schema_contract_drift")
        if (
            result.version.content_hash != proof.raw_body_sha256
            or result.version.content_hash != proof.normalized_result_content_sha256
        ):
            raise AcquisitionAuthorityError("live_normalized_raw_version_drift")
        if result.has_more or result.next_page_token is not None:
            raise AcquisitionAuthorityError("live_result_not_one_page")
        if result.row_count != _normalized_result_row_count(result.data):
            raise AcquisitionAuthorityError("live_normalized_row_count_drift")
        try:
            raw_payload = json.loads(
                fabric_data_plane.resolve_raw_response_body(proof.raw_evidence_ref)
            )
        except Exception as exc:
            raise AcquisitionAuthorityError(
                "live_raw_response_not_json",
                type(exc).__name__,
            ) from exc
        if (
            not isinstance(raw_payload, list)
            or len(raw_payload) < 2
            or not isinstance(raw_payload[0], Mapping)
            or not isinstance(raw_payload[1], list)
            or any(not isinstance(row, Mapping) for row in raw_payload[1])
        ):
            raise AcquisitionAuthorityError("live_raw_response_shape_drift")
        request_event = fabric_data_plane.resolve_journal_event_ref(proof.request_ref)
        request_value = request_event.get("request")
        if not isinstance(request_value, Mapping):
            raise AcquisitionAuthorityError("live_request_missing")
        request = {str(key): value for key, value in request_value.items()}
        filters = request.get("filters")
        if not isinstance(filters, Mapping):
            raise AcquisitionAuthorityError("live_request_scope_invalid")
        countries = filters.get("country")
        if (
            not isinstance(countries, Sequence)
            or isinstance(countries, (str, bytes, bytearray))
            or len(countries) != 1
        ):
            raise AcquisitionAuthorityError("live_request_scope_invalid")
        country_code = str(countries[0])
        date_start = str(request.get("date_start") or "")
        date_end = str(request.get("date_end") or "")
        page_size = request.get("page_size")
        metadata = raw_payload[0]
        raw_rows = raw_payload[1]
        try:
            metadata_values = (
                int(str(metadata.get("page"))),
                int(str(metadata.get("pages"))),
                int(str(metadata.get("per_page"))),
                int(str(metadata.get("total"))),
            )
        except (TypeError, ValueError) as exc:
            raise AcquisitionAuthorityError("live_raw_page_metadata_drift") from exc
        if metadata_values != (1, 1, page_size, len(raw_rows)):
            raise AcquisitionAuthorityError("live_raw_page_metadata_drift")
        expected_frame = fabric_connectors.normalize_worldbank_records(
            raw_rows,
            resolved.registration.request_dataset_id,
        )
        if isinstance(result.data, pd.DataFrame):
            actual_frame = result.data
        elif isinstance(result.data, Sequence) and not isinstance(
            result.data,
            (str, bytes, bytearray),
        ):
            actual_frame = pd.DataFrame(result.data)
        else:
            raise AcquisitionAuthorityError("live_normalized_payload_unsupported")
        if list(actual_frame.columns) != list(
            expected_frame.columns
        ) or not actual_frame.reset_index(drop=True).equals(expected_frame.reset_index(drop=True)):
            raise AcquisitionAuthorityError("live_normalized_raw_projection_drift")
        if any(
            row.get("indicator_id") != resolved.registration.request_dataset_id
            or row.get("country_code") != country_code
            or not _live_year_is_in_scope(
                row.get("year"),
                date_start=date_start,
                date_end=date_end,
            )
            for row in expected_frame.to_dict(orient="records")
        ):
            raise AcquisitionAuthorityError("live_normalized_scope_drift")

    @staticmethod
    def _reopen_artifact(
        artifact_store: ArtifactStore,
        artifact_id: ArtifactID,
        *,
        expected_kind: str | None = None,
    ) -> bytes:
        if not artifact_store.has(artifact_id):
            raise AcquisitionAuthorityError("live_artifact_unresolved", str(artifact_id))
        manifest = artifact_store.get_manifest(artifact_id)
        if expected_kind is not None and manifest.kind != expected_kind:
            raise AcquisitionAuthorityError("live_artifact_kind_drift", manifest.kind)
        return artifact_store.get_bytes(artifact_id)

    @classmethod
    def _reopen_artifact_ref(
        cls,
        artifact_store: ArtifactStore,
        ref: object,
        *,
        expected_kind: str | None = None,
    ) -> bytes:
        artifact_id = getattr(ref, "artifact_id", None)
        kind = getattr(ref, "kind", None)
        media_type = getattr(ref, "media_type", None)
        if not isinstance(artifact_id, ArtifactID):
            raise AcquisitionAuthorityError("live_artifact_ref_invalid")
        manifest = artifact_store.get_manifest(artifact_id)
        if manifest.kind != kind or manifest.media_type != media_type:
            raise AcquisitionAuthorityError("live_artifact_ref_manifest_drift")
        if expected_kind is not None and kind != expected_kind:
            raise AcquisitionAuthorityError("live_artifact_kind_drift", str(kind))
        return cls._reopen_artifact(
            artifact_store,
            artifact_id,
            expected_kind=expected_kind,
        )

    def _load_registry(self) -> AcquisitionAuthorityRegistry:
        if not self.registry_path.is_file():
            raise AcquisitionAuthorityError(
                "authority_registry_missing", self.registry_path.as_posix()
            )
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
            registry = AcquisitionAuthorityRegistry.model_validate(payload)
        except Exception as exc:
            raise AcquisitionAuthorityError(
                "authority_registry_invalid", type(exc).__name__
            ) from exc
        actual_baseline = _file_sha256(self.baseline_path)
        if actual_baseline != registry.baseline_content_sha256:
            raise AcquisitionAuthorityError("authority_baseline_identity_drift")
        return registry

    def _resolve_live_catalog(
        self,
        entry: AcquisitionAuthorityEntry,
    ) -> tuple[
        dict[str, object],
        str,
        str,
        str,
        AcquisitionDatasetRegistration,
    ]:
        con = duckdb.connect(str(self.baseline_path), read_only=True)
        try:
            rows = con.execute(
                """
                SELECT d.source, d.agency, d.title, d.description,
                       d.access_license, d.execution_tier,
                       x.connector_type, x.profile_id, x.source_locator,
                       b.request_dataset_id, b.metric_id, b.confidence
                FROM ds_datasets d
                JOIN ds_distributions x ON x.dataset_id = d.id
                JOIN ds_metric_bindings b
                  ON b.dataset_id = d.id AND b.distribution_id = x.id
                WHERE d.id = ? AND x.id = ? AND b.metric_id = ?
                  AND b.request_dataset_id = ?
                """,
                [
                    entry.source_catalog_dataset_id,
                    entry.source_catalog_distribution_id,
                    entry.upstream_metric_id,
                    entry.catalog_raw_variable,
                ],
            ).fetchall()
            if len(rows) != 1:
                raise AcquisitionAuthorityError("catalog_authority_edge_unresolved")
            values = rows[0]
            alignment_rows = con.execute(
                """
                SELECT raw_variable, canonical_var, method, confidence,
                       evidence, is_proxy, proxy_penalty
                FROM ds_variable_alignments
                WHERE dataset_id = ? AND raw_variable = ? AND canonical_var = ?
                """,
                [
                    entry.source_catalog_dataset_id,
                    entry.catalog_raw_variable,
                    entry.upstream_metric_id,
                ],
            ).fetchall()
            if len(alignment_rows) > 1:
                raise AcquisitionAuthorityError("catalog_authority_edge_ambiguous")
        finally:
            con.close()
        (
            source,
            agency,
            title,
            description,
            license_id,
            execution_tier,
            connector_id,
            profile_id,
            source_locator,
            request_dataset_id,
            metric_id,
            binding_confidence,
        ) = values
        if str(execution_tier) not in {"fetchable", "transport_ready"}:
            raise AcquisitionAuthorityError("catalog_execution_tier_not_executable")
        catalog_unit = derive_catalog_unit_from_text(f"{title or ''} {description or ''}")
        if catalog_unit is None:
            raise AcquisitionAuthorityError("catalog_unit_unresolved")
        if normalize_acquisition_unit(entry.raw_unit) != catalog_unit:
            raise AcquisitionAuthorityError(
                "catalog_unit_mismatch",
                f"{entry.raw_unit}:{catalog_unit}",
            )
        if entry.unit_transform == "identity" and (
            normalize_acquisition_unit(entry.canonical_unit) != catalog_unit
        ):
            raise AcquisitionAuthorityError("catalog_identity_unit_mismatch")

        if alignment_rows:
            (
                catalog_raw_variable,
                canonical_var,
                alignment_method,
                alignment_confidence,
                alignment_evidence,
                is_proxy,
                proxy_penalty,
            ) = alignment_rows[0]
            if float(entry.alignment_confidence) > float(alignment_confidence) + 1e-9:
                raise AcquisitionAuthorityError("authority_alignment_inflated")
            catalog_alignment_status = "owner_alignment_resolved"
            generic_alignment_score = None
        else:
            owner_score = score_variable_pair(
                left_name=entry.target_variable,
                right_name=str(metric_id),
                left_unit=entry.canonical_unit,
                right_unit=entry.raw_unit,
            )
            if (
                entry.alignment_method != "semantic"
                or abs(float(entry.alignment_confidence) - owner_score.overall_score) > 1e-9
            ):
                raise AcquisitionAuthorityError("authority_alignment_owner_drift")
            if float(entry.alignment_confidence) > float(binding_confidence) + 1e-9:
                raise AcquisitionAuthorityError("authority_alignment_inflated")
            catalog_raw_variable = entry.catalog_raw_variable
            canonical_var = entry.upstream_metric_id
            alignment_method = "semantic"
            alignment_confidence = owner_score.overall_score
            alignment_evidence = ";".join(owner_score.evidence)
            is_proxy = entry.is_proxy
            proxy_penalty = entry.proxy_penalty
            catalog_alignment_status = "registry_last_mile_owner_scored"
            generic_alignment_score = owner_score.model_dump(mode="json")
        projection = {
            "source_catalog_dataset_id": entry.source_catalog_dataset_id,
            "source_catalog_distribution_id": entry.source_catalog_distribution_id,
            "source": source,
            "agency": agency,
            "title": title,
            "description": description,
            "license_id": license_id,
            "execution_tier": execution_tier,
            "connector_id": connector_id,
            "profile_id": profile_id,
            "source_locator": source_locator,
            "request_dataset_id": request_dataset_id,
            "metric_id": metric_id,
            "binding_confidence": binding_confidence,
            "catalog_raw_variable": catalog_raw_variable,
            "canonical_var": canonical_var,
            "catalog_unit": catalog_unit,
            "catalog_alignment_status": catalog_alignment_status,
            "generic_alignment_score": generic_alignment_score,
            "alignment_method": alignment_method,
            "alignment_confidence": alignment_confidence,
            "alignment_evidence": alignment_evidence,
            "is_proxy": is_proxy,
            "proxy_penalty": proxy_penalty,
        }
        placeholder = build_metric_field_binding(
            dataset_id=entry.landing_dataset_id,
            distribution_id=entry.landing_distribution_id,
            raw_field=entry.raw_field,
            canonical_variable=entry.target_variable,
            raw_unit=entry.raw_unit,
            canonical_unit=entry.canonical_unit,
            unit_transform=entry.unit_transform,
            unit_transform_ref=entry.unit_transform_ref,
            alignment_method=entry.alignment_method,
            alignment_confidence=entry.alignment_confidence,
            is_proxy=entry.is_proxy,
            proxy_penalty=entry.proxy_penalty,
            evidence_refs=entry.evidence_refs,
            aggregation_method=entry.aggregation_method,
            valid_min=entry.valid_min,
            valid_max=entry.valid_max,
        )
        registration = AcquisitionDatasetRegistration(
            catalog_dataset_id=entry.landing_dataset_id,
            source=str(source),
            agency=str(agency or ""),
            request_dataset_id=str(request_dataset_id),
            distribution_id=entry.landing_distribution_id,
            connector_id=str(connector_id),
            source_profile_id=str(profile_id),
            source_locator=str(source_locator),
            title=entry.title,
            description=entry.description,
            metric_id=entry.target_variable,
            execution_tier=str(execution_tier),
            access_license=str(license_id),
            country_codes=entry.country_codes,
            temporal_start=entry.temporal_start,
            temporal_end=entry.temporal_end,
            field_binding=placeholder,
        )
        license_projection = {
            "dataset_id": entry.source_catalog_dataset_id,
            "access_license": str(license_id),
        }
        if self.baseline_owner_ref is None:
            raise AcquisitionAuthorityError("baseline_owner_ref_unprovisioned")
        return (
            projection,
            str(license_id),
            (
                f"{self.baseline_owner_ref}"
                "#ds_datasets/"
                f"{entry.source_catalog_dataset_id}/access_license"
            ),
            fabric_data_plane.content_sha256(license_projection),
            registration,
        )

    def _resolve_local_source(
        self,
        entry: AcquisitionAuthorityEntry,
        *,
        expected_trust_registry_sha256: str | None,
    ) -> tuple[
        dict[str, object],
        str,
        str,
        str,
        AcquisitionDatasetRegistration,
    ]:
        relative = Path(str(entry.local_source_path))
        if relative.is_absolute() or ".." in relative.parts:
            raise AcquisitionAuthorityError("local_source_path_unsafe")
        source_path = (self.repo_root / relative).resolve()
        if not source_path.is_relative_to(self.repo_root):
            raise AcquisitionAuthorityError("local_source_path_unsafe")
        source_hash = _file_sha256(source_path)
        if source_hash != entry.local_source_sha256:
            raise AcquisitionAuthorityError("local_source_content_drift")
        receipt_relative = Path(str(entry.local_rights_receipt_path))
        if receipt_relative.is_absolute() or ".." in receipt_relative.parts:
            raise AcquisitionAuthorityError("local_rights_receipt_path_unsafe")
        receipt_path = (self.repo_root / receipt_relative).resolve()
        if not receipt_path.is_relative_to(self.repo_root):
            raise AcquisitionAuthorityError("local_rights_receipt_path_unsafe")
        if _file_sha256(receipt_path) != entry.local_rights_receipt_sha256:
            raise AcquisitionAuthorityError("local_rights_receipt_content_drift")
        try:
            rights = LocalSourceRightsReceipt.model_validate_json(receipt_path.read_bytes())
        except Exception as exc:
            raise AcquisitionAuthorityError(
                "local_rights_receipt_invalid",
                type(exc).__name__,
            ) from exc
        if not expected_trust_registry_sha256:
            raise AcquisitionAuthorityError("local_rights_trust_anchor_unprovisioned")
        trust_relative = DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY
        document_relative = _safe_repo_relative_path(
            rights.rights_document_path,
            code="local_rights_document_path",
        )
        recomputed_rights, declaration, trust_registry = _derive_local_source_rights_receipt(
            root=self.repo_root,
            source_relative=relative,
            document_relative=document_relative,
            trust_relative=trust_relative,
            expected_trust_file_sha256=expected_trust_registry_sha256,
        )
        if (
            rights != recomputed_rights
            or rights.source_content_sha256 != source_hash
            or rights.license_id != entry.local_license_id
        ):
            raise AcquisitionAuthorityError("local_rights_receipt_recomputation_drift")
        placeholder = build_metric_field_binding(
            dataset_id=entry.landing_dataset_id,
            distribution_id=entry.landing_distribution_id,
            raw_field=entry.raw_field,
            canonical_variable=entry.target_variable,
            raw_unit=entry.raw_unit,
            canonical_unit=entry.canonical_unit,
            unit_transform=entry.unit_transform,
            unit_transform_ref=entry.unit_transform_ref,
            alignment_method=entry.alignment_method,
            alignment_confidence=entry.alignment_confidence,
            is_proxy=entry.is_proxy,
            proxy_penalty=entry.proxy_penalty,
            evidence_refs=entry.evidence_refs,
            aggregation_method=entry.aggregation_method,
            valid_min=entry.valid_min,
            valid_max=entry.valid_max,
        )
        registration = AcquisitionDatasetRegistration(
            catalog_dataset_id=entry.landing_dataset_id,
            source="policyos_acquisition_local_lift",
            agency="PolicyOS owner-validated local source",
            request_dataset_id=source_path.name,
            distribution_id=entry.landing_distribution_id,
            connector_id="local.parquet",
            source_profile_id="local_parquet",
            source_locator=f"repo://{relative.as_posix()}",
            title=entry.title,
            description=entry.description,
            metric_id=entry.target_variable,
            execution_tier="transport_ready",
            access_license=rights.license_id,
            country_codes=entry.country_codes,
            temporal_start=entry.temporal_start,
            temporal_end=entry.temporal_end,
            field_binding=placeholder,
        )
        projection = {
            "local_source_path": relative.as_posix(),
            "local_source_sha256": source_hash,
            "local_rights_receipt_id": rights.receipt_id,
            "local_rights_receipt_sha256": entry.local_rights_receipt_sha256,
            "local_rights_document_sha256": rights.rights_document_sha256,
            "local_rights_declaration_id": declaration.declaration_id,
            "local_rights_trust_registry_sha256": trust_registry.content_sha256,
            "local_rights_public_key_sha256": rights.public_key_sha256,
        }
        return (
            projection,
            rights.license_id,
            f"repo://{document_relative.as_posix()}",
            rights.rights_document_sha256,
            registration,
        )

    def _resolve_l5(
        self,
        family_id: str,
        *,
        expected_content_sha256: str,
    ) -> ResolvedL5Trust:
        if not self.l5_path.is_file():
            raise AcquisitionAuthorityError("l5_measurement_registry_missing")
        raw = self.l5_path.read_bytes()
        owner_hash = f"sha256:{hashlib.sha256(raw).hexdigest()}"
        if owner_hash != expected_content_sha256:
            raise AcquisitionAuthorityError("l5_measurement_registry_content_drift")
        try:
            payload = json.loads(raw)
            coverage = float(_mapping(payload.get("coverage_rules"))[family_id])
            tiers = _mapping(payload.get("trust_tiers"))
        except Exception as exc:
            raise AcquisitionAuthorityError("l5_family_unresolved", family_id) from exc
        eligible: list[tuple[float, float, float, str, Mapping[str, object]]] = []
        for tier_id, value in tiers.items():
            if not isinstance(value, Mapping):
                continue
            lower = float(value.get("min_coverage") or 0.0)
            upper = float(value.get("max_coverage") or 1.0)
            if lower - 1e-9 <= coverage <= upper + 1e-9:
                eligible.append(
                    (
                        lower,
                        float(value.get("trust_cap") or 0.0),
                        float(value.get("trust_multiplier") or 0.0),
                        str(tier_id),
                        value,
                    )
                )
        if not eligible:
            raise AcquisitionAuthorityError("l5_trust_tier_unresolved", family_id)
        _, trust_cap, trust_multiplier, tier_id, row = max(eligible)
        return ResolvedL5Trust(
            family_id=family_id,
            tier=str(row.get("tier") or tier_id),
            trust_cap=trust_cap,
            trust_multiplier=trust_multiplier,
            authority_ref=f"{self.l5_owner_ref}#/trust_tiers/{tier_id}",
            owner_ref=self.l5_owner_ref,
            owner_content_sha256=owner_hash,
        )


def derive_license_disposition(value: str) -> LicenseDisposition:
    """Derive one license disposition from the canonical narrow policy."""

    normalized = value.strip().lower().replace("_", "-")
    if normalized in {
        "cc-by-4.0",
        "cc-by-3.0",
        "cc0-1.0",
        "odc-by-1.0",
        "pddl-1.0",
    }:
        return LicenseDisposition.ADMISSIBLE_OPEN
    if normalized in {"all-rights-reserved", "proprietary", "restricted"}:
        return LicenseDisposition.RESTRICTED
    return LicenseDisposition.UNCLEAR


def normalize_acquisition_unit(value: str) -> str:
    """Normalize the narrow catalog units admitted by the acquisition owner."""

    text = value.strip().casefold().replace("_", " ").replace("-", " ")
    text = " ".join(text.split())
    aliases = {
        "$": "usd",
        "current usd": "usd",
        "current us dollars": "usd",
        "percent of gdp": "percent_gdp",
        "% of gdp": "percent_gdp",
        "lcu": "local_currency",
        "current lcu": "local_currency",
        "price index": "index",
    }
    return aliases.get(text, text.replace(" ", "_"))


def derive_catalog_unit_from_text(value: str) -> str | None:
    """Derive a source unit from catalog-owned title and description text.

    This deliberately recognizes unit families, not indicator IDs. Ambiguous or
    absent units fail closed so a registry row cannot mint its own unit authority.
    """

    text = " ".join(value.casefold().replace("\u00a0", " ").split())
    candidates: set[str] = set()
    if ("%" in text or "percent" in text) and "gdp" in text:
        candidates.add("percent_gdp")
    if any(
        token in text
        for token in (
            "current us$",
            "current us $",
            "current usd",
            "current u.s. dollar",
            "current us dollar",
        )
    ):
        candidates.add("usd")
    if "current lcu" in text or "current local currenc" in text:
        candidates.add("local_currency")
    if "price index" in text or re.search(r"\bindex\s*\([^)]*=\s*100\)", text):
        candidates.add("index")
    if len(candidates) != 1:
        return None
    return candidates.pop()


def _normalized_result_row_count(data: object) -> int:
    if isinstance(data, pd.DataFrame):
        return len(data.index)
    if isinstance(data, Mapping):
        return 1
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        return len(data)
    raise AcquisitionAuthorityError(
        "live_normalized_payload_unsupported",
        type(data).__name__,
    )


def _normalized_fetch_result_body(result: FetchResult[Any]) -> bytes:
    data = result.data
    if isinstance(data, pd.DataFrame):
        # Round through pandas' JSON encoder so numpy scalars and timestamps
        # become plain JSON values before canonicalization.
        payload: object = json.loads(
            data.to_json(
                orient="records",
                date_format="iso",
                date_unit="us",
                double_precision=15,
            )
        )
    elif isinstance(data, Mapping):
        payload = dict(data)
    elif isinstance(data, Sequence) and not isinstance(
        data,
        (str, bytes, bytearray),
    ):
        payload = list(data)
    else:
        raise AcquisitionAuthorityError(
            "live_normalized_payload_unsupported",
            type(data).__name__,
        )
    return canonical_json_bytes(payload)


def _live_date_scope_is_admissible(
    entry: AcquisitionAuthorityEntry,
    date_start: str,
    date_end: str,
) -> bool:
    """Recompute whether one whole-year request lies within owner authority."""

    if (
        len(date_start) != 10
        or len(date_end) != 10
        or not date_start[:4].isdigit()
        or not date_end[:4].isdigit()
        or date_start[4:] != "-01-01"
        or date_end[4:] != "-12-31"
    ):
        return False
    try:
        start_year = int(date_start[:4])
        end_year = int(date_end[:4])
        owner_start, owner_end = resolve_live_temporal_bounds(entry)
    except (TypeError, ValueError, AcquisitionAuthorityError):
        return False
    if owner_start is None or owner_end is None:
        return start_year <= end_year
    return owner_start <= start_year <= end_year <= owner_end


def resolve_live_temporal_bounds(
    entry: AcquisitionAuthorityEntry,
) -> tuple[int | None, int | None]:
    """Resolve optional catalog temporal bounds without inventing closed scope."""

    if entry.temporal_start is None and entry.temporal_end is None:
        return None, None
    if entry.temporal_start is None or entry.temporal_end is None:
        raise AcquisitionAuthorityError("live_authority_temporal_scope_invalid")
    start_text = entry.temporal_start.strip()
    end_text = entry.temporal_end.strip()
    if not re.match(r"^\d{4}(?:$|[-T])", start_text) or not re.match(
        r"^\d{4}(?:$|[-T])",
        end_text,
    ):
        raise AcquisitionAuthorityError("live_authority_temporal_scope_invalid")
    owner_start = int(start_text[:4])
    owner_end = int(end_text[:4])
    if owner_end < owner_start:
        raise AcquisitionAuthorityError("live_authority_temporal_scope_invalid")
    return owner_start, owner_end


def _live_year_is_in_scope(
    value: object,
    *,
    date_start: str,
    date_end: str,
) -> bool:
    """Return whether one normalized observation year belongs to the request."""

    if isinstance(value, bool):
        return False
    try:
        year = int(str(value))
        start_year = int(date_start[:4])
        end_year = int(date_end[:4])
    except (TypeError, ValueError):
        return False
    return start_year <= year <= end_year


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise AcquisitionAuthorityError("authority_source_missing", path.as_posix())
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _load_authority_provision(
    path: Path,
) -> tuple[AcquisitionAuthorityProvision, str]:
    if not path.is_file():
        raise AcquisitionAuthorityError(
            "acquisition_authority_provision_missing",
            path.as_posix(),
        )
    raw = path.read_bytes()
    try:
        provision = AcquisitionAuthorityProvision.model_validate_json(raw)
    except Exception as exc:
        raise AcquisitionAuthorityError(
            "acquisition_authority_provision_invalid",
            type(exc).__name__,
        ) from exc
    return provision, f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _derive_local_source_rights_receipt(
    *,
    root: Path,
    source_relative: Path,
    document_relative: Path,
    trust_relative: Path,
    expected_trust_file_sha256: str | None,
) -> tuple[
    LocalSourceRightsReceipt,
    LocalSourceRightsDeclaration,
    LocalRightsTrustRegistry,
]:
    """Single behavioral verifier shared by receipt writing and admission."""

    if document_relative == source_relative:
        raise AcquisitionAuthorityError("local_rights_document_is_source")
    source = _resolve_repo_file(root, source_relative, code="local_source_path")
    document = _resolve_repo_file(
        root,
        document_relative,
        code="local_rights_document_path",
    )
    source_sha = _file_sha256(source)
    document_sha = _file_sha256(document)
    try:
        declaration = LocalSourceRightsDeclaration.model_validate_json(document.read_bytes())
    except Exception as exc:
        raise AcquisitionAuthorityError(
            "local_rights_document_invalid",
            type(exc).__name__,
        ) from exc
    if (
        declaration.source_path != source_relative.as_posix()
        or declaration.source_content_sha256 != source_sha
    ):
        raise AcquisitionAuthorityError("local_rights_document_source_drift")
    trust_path = _resolve_repo_file(
        root,
        trust_relative,
        code="local_rights_trust_registry_path",
    )
    trust_registry = _load_local_rights_trust_registry(
        trust_path,
        expected_file_sha256=expected_trust_file_sha256,
    )
    trusted = _verify_local_rights_declaration(
        declaration,
        trust_registry=trust_registry,
    )
    public_key = base64.b64decode(
        trusted.ed25519_public_key_base64,
        validate=True,
    )
    values: dict[str, object] = {
        "source_path": source_relative.as_posix(),
        "source_content_sha256": source_sha,
        "license_id": declaration.license_id,
        "authority_id": declaration.authority_id,
        "rights_authority": declaration.rights_authority,
        "authority_ref": declaration.authority_ref,
        "rights_document_path": document_relative.as_posix(),
        "rights_document_sha256": document_sha,
        "rights_declaration_id": declaration.declaration_id,
        "trust_registry_content_sha256": trust_registry.content_sha256,
        "public_key_sha256": f"sha256:{hashlib.sha256(public_key).hexdigest()}",
    }
    provisional = LocalSourceRightsReceipt.model_construct(
        receipt_id="local-rights:sha256:" + "0" * 64,
        **values,
    )
    receipt = LocalSourceRightsReceipt(
        receipt_id=(
            "local-rights:" + fabric_data_plane.content_sha256(provisional.identity_payload())
        ),
        **values,
    )
    return receipt, declaration, trust_registry


def _load_local_rights_trust_registry(
    path: Path,
    *,
    expected_file_sha256: str | None = None,
) -> LocalRightsTrustRegistry:
    if not path.is_file():
        raise AcquisitionAuthorityError(
            "local_rights_trust_registry_missing",
            path.as_posix(),
        )
    try:
        registry = LocalRightsTrustRegistry.model_validate_json(path.read_bytes())
    except Exception as exc:
        raise AcquisitionAuthorityError(
            "local_rights_trust_registry_invalid",
            type(exc).__name__,
        ) from exc
    actual = _file_sha256(path)
    if expected_file_sha256 is not None and actual != expected_file_sha256:
        raise AcquisitionAuthorityError("local_rights_trust_registry_content_drift")
    return registry


def _verify_local_rights_declaration(
    declaration: LocalSourceRightsDeclaration,
    *,
    trust_registry: LocalRightsTrustRegistry,
) -> LocalRightsTrustedAuthority:
    matches = tuple(
        authority
        for authority in trust_registry.authorities
        if authority.authority_id == declaration.authority_id
    )
    if len(matches) != 1:
        raise AcquisitionAuthorityError("local_rights_signing_authority_unresolved")
    trusted = matches[0]
    if (
        declaration.rights_authority != trusted.rights_authority
        or declaration.authority_ref != trusted.authority_ref
        or declaration.license_id not in trusted.admissible_license_ids
    ):
        raise AcquisitionAuthorityError("local_rights_signing_authority_drift")
    try:
        public_key = base64.b64decode(
            trusted.ed25519_public_key_base64,
            validate=True,
        )
        signature = base64.b64decode(declaration.signature_base64, validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature,
            canonical_json_bytes(declaration.signed_payload()),
        )
    except (InvalidSignature, ValueError) as exc:
        raise AcquisitionAuthorityError("local_rights_signature_invalid") from exc
    return trusted


def _safe_repo_relative_path(value: str, *, code: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise AcquisitionAuthorityError(f"{code}_unsafe")
    return path


def _resolve_repo_file(root: Path, relative: Path, *, code: str) -> Path:
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise AcquisitionAuthorityError(f"{code}_unsafe")
    if not resolved.is_file():
        raise AcquisitionAuthorityError(f"{code}_missing", resolved.as_posix())
    return resolved


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AcquisitionAuthorityError("authority_mapping_required")
    return {str(key): item for key, item in value.items()}


__all__ = [
    "ACQUISITION_AUTHORITY_PROVISION_SCHEMA_VERSION",
    "ACQUISITION_AUTHORITY_SCHEMA_VERSION",
    "DEFAULT_ACQUISITION_AUTHORITY_PROVISION",
    "DEFAULT_ACQUISITION_AUTHORITY_REGISTRY",
    "DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY",
    "LIVE_SOURCE_EXECUTION_EVIDENCE_SCHEMA_VERSION",
    "LOCAL_RIGHTS_TRUST_REGISTRY_SCHEMA_VERSION",
    "LOCAL_SOURCE_RIGHTS_DECLARATION_SCHEMA_VERSION",
    "LOCAL_SOURCE_RIGHTS_RECEIPT_SCHEMA_VERSION",
    "AcquisitionAuthorityEntry",
    "AcquisitionAuthorityError",
    "AcquisitionAuthorityProvision",
    "AcquisitionAuthorityRegistry",
    "AuthoritySchemaColumn",
    "CanonicalAcquisitionAuthority",
    "LicenseDisposition",
    "LiveHarnessReceiptProvisionEntry",
    "LiveSourceExecutionEvidence",
    "LocalRightsTrustRegistry",
    "LocalRightsTrustedAuthority",
    "LocalSourceRightsDeclaration",
    "LocalSourceRightsReceipt",
    "ResolvedAcquisitionAuthority",
    "ResolvedL5Trust",
    "ResolvedLiveHarnessReceipt",
    "build_acquisition_authority_provision",
    "build_authority_entry",
    "build_authority_registry",
    "build_live_source_execution_evidence",
    "build_local_rights_trust_registry",
    "build_local_source_rights_declaration",
    "derive_catalog_unit_from_text",
    "derive_license_disposition",
    "normalize_acquisition_unit",
    "resolve_live_temporal_bounds",
    "verify_local_source_rights",
]
