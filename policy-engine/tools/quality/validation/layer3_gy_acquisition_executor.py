"""Recomputing owners for the GY-N13b acquisition execution evidence.

This module is intentionally data-plane only.  It derives an executable target
from the frozen N13a demand denominator, the immutable catalog, and the L6 slot
vocabulary.  It never executes a connector merely to select a target.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import socket
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self
from unittest.mock import patch

import duckdb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import ArtifactID, FileSystemCAS
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
    VariablePairAlignmentScore,  # noqa: TC001 - Pydantic resolves this at runtime.
)
from polisyos.fabric.connectors.sources._contracts import WDI_GENERIC_SCHEMA
from polisyos.fabric.data_plane import (
    JournalEventRef,
    LiveAttemptTerminal,
    LiveMetadataExecutionAuthorization,
    LiveMetadataHarnessReceipt,
    LiveTransportTrace,
    build_live_metadata_execution_authorization,
    canonical_json_bytes,
    content_sha256,
    resolve_journal_event_ref,
    resolve_live_attempt_terminals,
    resolve_live_transport_trace,
    resolve_raw_response_body,
)

TARGET_SELECTION_SCHEMA_VERSION = "policyos.layer3.gy.n13b.live_target_selection.v1"
_EXECUTABLE_TIERS = frozenset({"fetchable", "transport_ready"})
_ALIVE_LIVENESS_PREFIX = "alive_"
DEFAULT_TARGET_AUTHORITY_REGISTRY = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_registry.json"
)
DEFAULT_TARGET_AUTHORITY_PROVISION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_provision.json"
)
DEFAULT_TARGET_HARNESS_RECEIPT = Path(
    "architecture/policy_design_case/layer3_gy_n13b_worldbank_government_balance_harness.json"
)
DEFAULT_R1_FORENSIC_RECEIPT = Path(
    "architecture/policy_design_case/layer3_gy_n13b_r1_forensic_receipt.json"
)
DEFAULT_METADATA_PROBE_OWNER = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13b_worldbank_government_balance_metadata_owner.json"
)
DEFAULT_METADATA_EXECUTION_EVIDENCE = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13b_worldbank_government_balance_metadata_evidence.json"
)
DEFAULT_CARRIER_LIVENESS_UPDATE = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json"
)


class CarrierDataDisposition(StrEnum):
    """Typed R1 outcome recomputed only from paid response bytes."""

    CARRIER_RETIRED_OR_INVALID = "carrier_retired_or_invalid"
    NO_DATA_FOR_SCOPE = "no_data_for_scope"
    RESPONSE_SHAPE_UNCLASSIFIED = "response_shape_unclassified"


class IndicatorMetadataDisposition(StrEnum):
    """Typed exact-indicator disposition derived after metadata journaling."""

    CARRIER_CURRENT = "carrier_current"
    CARRIER_RETIRED_OR_INVALID = "carrier_retired_or_invalid"
    RESPONSE_SHAPE_UNCLASSIFIED = "response_shape_unclassified"


class AcquisitionSelectionError(RuntimeError):
    """Typed refusal raised when source evidence cannot select one live carrier."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail or code}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WorldBankDataResponseClassification(_StrictModel):
    """R1 response classification bound to exact immutable bytes."""

    body_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    byte_count: int = Field(ge=0)
    disposition: CarrierDataDisposition
    row_count: int | None = Field(default=None, ge=0)
    api_message_count: int = Field(ge=0)


class WorldBankIndicatorMetadataClassification(_StrictModel):
    """Current/retired metadata result with only owner-declared fields."""

    body_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    byte_count: int = Field(ge=0)
    disposition: IndicatorMetadataDisposition
    indicator_id: str = Field(min_length=1)
    source_id: str | None = None
    source_name: str | None = None
    unit: str | None = None
    coverage_start: str | None = None
    coverage_end: str | None = None
    declared_coverage: str = Field(min_length=1)
    api_message_count: int = Field(ge=0)


class R1AttemptForensicProjection(_StrictModel):
    """Narrow verified projection of one already-paid data attempt."""

    attempt_id: str = Field(min_length=1)
    request_sequence: int = Field(ge=1)
    request_event_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_dataset_id: str = Field(min_length=1)
    terminal_event_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    terminal_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    terminal_outcome: str = Field(min_length=1)
    terminal_failure_code: str = Field(min_length=1)
    raw_evidence_event_sha256: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    raw_body_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    raw_byte_count: int | None = Field(default=None, ge=0)
    http_status_code: int | None = Field(default=None, ge=100, le=599)
    max_elapsed_seconds: float = Field(ge=0.0)
    projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _attempt_projection_is_recomputed(self) -> Self:
        raw_values = (
            self.raw_evidence_event_sha256,
            self.raw_body_sha256,
            self.raw_byte_count,
        )
        if any(value is None for value in raw_values) != all(value is None for value in raw_values):
            raise ValueError("R1 raw evidence projection must be complete or absent")
        if self.http_status_code is not None and self.raw_body_sha256 is None:
            raise ValueError("R1 HTTP status requires raw evidence")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("R1 attempt projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the exact attempt projection without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class R1ForensicReceipt(_StrictModel):
    """E10 receipt binding the paid journal prefix, CAS bytes, and R1 class."""

    schema_version: Literal["policyos.layer3.gy.n13b.r1_forensics.v1"] = (
        "policyos.layer3.gy.n13b.r1_forensics.v1"
    )
    journal_ref: str = Field(min_length=1)
    journal_prefix_byte_length: int = Field(gt=0)
    journal_prefix_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cas_blob_ref: str = Field(min_length=1)
    cas_manifest_ref: str = Field(min_length=1)
    cas_blob_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_dataset_id: str = Field(min_length=1)
    attempts: tuple[R1AttemptForensicProjection, ...] = Field(min_length=1)
    decisive_attempt_id: str = Field(min_length=1)
    classification: WorldBankDataResponseClassification
    receipt_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _receipt_is_recomputed(self) -> Self:
        attempt_ids = tuple(attempt.attempt_id for attempt in self.attempts)
        if len(attempt_ids) != len(set(attempt_ids)):
            raise ValueError("R1 attempt denominator must be unique")
        if tuple(attempt.request_sequence for attempt in self.attempts) != tuple(
            sorted(attempt.request_sequence for attempt in self.attempts)
        ):
            raise ValueError("R1 attempts must preserve journal order")
        decisive = tuple(
            attempt for attempt in self.attempts if attempt.attempt_id == self.decisive_attempt_id
        )
        if (
            len(decisive) != 1
            or decisive[0].raw_body_sha256 != self.classification.body_sha256
            or decisive[0].raw_byte_count != self.classification.byte_count
            or self.cas_blob_sha256 != self.classification.body_sha256
        ):
            raise ValueError("R1 decisive bytes must bind journal, CAS, and classification")
        if any(attempt.request_dataset_id != self.request_dataset_id for attempt in self.attempts):
            raise ValueError("R1 attempt denominator must preserve the exact carrier")
        if self.receipt_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("R1 forensic receipt identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the immutable forensic projection without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "receipt_sha256"
        }


class MetadataProbeOwner(_StrictModel):
    """Exact zero-network owner needed to authorize one metadata call."""

    schema_version: Literal["policyos.layer3.gy.n13b.metadata_probe_owner.v1"] = (
        "policyos.layer3.gy.n13b.metadata_probe_owner.v1"
    )
    r1_receipt_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    baseline_ref: str = Field(min_length=1)
    baseline_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request: dict[str, Any]
    harness: LiveMetadataHarnessReceipt
    authorization: LiveMetadataExecutionAuthorization
    owner_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _owner_is_recomputed(self) -> Self:
        if (
            self.authorization.harness != self.harness
            or self.authorization.request_sha256 != content_sha256(self.request)
            or self.authorization.baseline_sha256 != self.baseline_sha256
            or self.request.get("variable_id") != self.harness.request_variable
            or self.request.get("request_variables") != [self.harness.request_variable]
            or self.request.get("call_class") != "indicator_metadata"
        ):
            raise ValueError("metadata probe owner projections must preserve exact scope")
        if self.owner_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("metadata probe owner identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the timestamp-free metadata owner projection."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "owner_sha256"
        }


class MetadataProbeExecutionEvidence(_StrictModel):
    """Reopened journal/CAS projection for the single bounded R2 call."""

    schema_version: Literal["policyos.layer3.gy.n13b.metadata_probe_evidence.v1"] = (
        "policyos.layer3.gy.n13b.metadata_probe_evidence.v1"
    )
    owner_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    attempt_id: str = Field(min_length=1)
    baseline_before_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    baseline_after_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_ref: JournalEventRef
    raw_evidence_ref: JournalEventRef | None = None
    raw_artifact_id: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    raw_body_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    raw_byte_count: int | None = Field(default=None, ge=0)
    classification: WorldBankIndicatorMetadataClassification | None = None
    transport_trace: LiveTransportTrace | None = None
    terminal: LiveAttemptTerminal
    call_count: int = Field(ge=0, le=1)
    quarantine: Literal[True] = True
    response_admitted: Literal[False] = False
    evidence_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _evidence_is_recomputed(self) -> Self:
        if self.baseline_before_sha256 != self.baseline_after_sha256:
            raise ValueError("metadata probe cannot mutate the epoch-0 baseline")
        if (
            self.request_ref.event_kind != "request"
            or self.terminal.attempt_id != self.attempt_id
            or self.terminal.request_ref != self.request_ref
        ):
            raise ValueError("metadata evidence owner/request projection is invalid")
        raw_values = (
            self.raw_evidence_ref,
            self.raw_artifact_id,
            self.raw_body_sha256,
            self.raw_byte_count,
            self.classification,
            self.transport_trace,
        )
        if any(value is None for value in raw_values) != all(value is None for value in raw_values):
            raise ValueError("metadata raw evidence projection must be complete or absent")
        if self.raw_evidence_ref is None:
            if self.terminal.raw_evidence_ref is not None:
                raise ValueError("metadata terminal raw response cannot be omitted")
        else:
            assert self.classification is not None
            assert self.transport_trace is not None
            if (
                self.raw_evidence_ref.event_kind != "raw_response"
                or self.terminal.raw_evidence_ref != self.raw_evidence_ref
                or self.raw_artifact_id != self.classification.body_sha256
                or self.raw_body_sha256 != self.classification.body_sha256
                or self.raw_byte_count != self.classification.byte_count
                or self.transport_trace.raw_evidence_ref != self.raw_evidence_ref
                or self.transport_trace.call_count != self.call_count
            ):
                raise ValueError("metadata raw evidence identities must agree")
        if self.evidence_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("metadata execution evidence identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the exact evidence projection without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "evidence_sha256"
        }


def classify_worldbank_data_response(body: bytes) -> WorldBankDataResponseClassification:
    """Classify paid World Bank data bytes into the exact R1 vocabulary."""

    body_sha = f"sha256:{hashlib.sha256(body).hexdigest()}"
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    messages = _worldbank_api_messages(payload)
    disposition = CarrierDataDisposition.RESPONSE_SHAPE_UNCLASSIFIED
    row_count: int | None = None
    if messages:
        disposition = CarrierDataDisposition.CARRIER_RETIRED_OR_INVALID
    elif (
        isinstance(payload, list)
        and len(payload) == 2
        and isinstance(payload[0], Mapping)
        and _nonbool_int(payload[0].get("total")) == 0
        and payload[1] is None
    ):
        disposition = CarrierDataDisposition.NO_DATA_FOR_SCOPE
        row_count = 0
    return WorldBankDataResponseClassification(
        body_sha256=body_sha,
        byte_count=len(body),
        disposition=disposition,
        row_count=row_count,
        api_message_count=len(messages),
    )


def classify_worldbank_indicator_metadata(
    body: bytes,
    *,
    indicator_id: str,
) -> WorldBankIndicatorMetadataClassification:
    """Classify an exact metadata response without inferring missing coverage."""

    requested = str(indicator_id).strip()
    if not requested:
        raise AcquisitionSelectionError("metadata_indicator_id_missing")
    body_sha = f"sha256:{hashlib.sha256(body).hexdigest()}"
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    messages = _worldbank_api_messages(payload)
    disposition = IndicatorMetadataDisposition.RESPONSE_SHAPE_UNCLASSIFIED
    record: Mapping[str, object] | None = None
    if messages:
        disposition = IndicatorMetadataDisposition.CARRIER_RETIRED_OR_INVALID
    elif isinstance(payload, list) and len(payload) == 2 and isinstance(payload[0], Mapping):
        total = _nonbool_int(payload[0].get("total"))
        rows = payload[1]
        if total == 0 and rows in (None, []):
            disposition = IndicatorMetadataDisposition.CARRIER_RETIRED_OR_INVALID
        elif total == 1 and isinstance(rows, list) and len(rows) == 1:
            candidate = rows[0]
            if isinstance(candidate, Mapping) and candidate.get("id") == requested:
                disposition = IndicatorMetadataDisposition.CARRIER_CURRENT
                record = candidate
    source = record.get("source") if record is not None else None
    source_mapping = source if isinstance(source, Mapping) else {}
    coverage_start = _optional_owner_string(record, "coverageStart", "coverage_start")
    coverage_end = _optional_owner_string(record, "coverageEnd", "coverage_end")
    declared_coverage = (
        f"{coverage_start or 'open'}:{coverage_end or 'open'}"
        if coverage_start is not None or coverage_end is not None
        else "not_declared_by_indicator_metadata_endpoint"
    )
    return WorldBankIndicatorMetadataClassification(
        body_sha256=body_sha,
        byte_count=len(body),
        disposition=disposition,
        indicator_id=requested,
        source_id=_optional_string(source_mapping.get("id")),
        source_name=_optional_string(source_mapping.get("value")),
        unit=_optional_string(record.get("unit")) if record is not None else None,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        declared_coverage=declared_coverage,
        api_message_count=len(messages),
    )


def derive_r1_forensic_receipt(
    *,
    journal_path: Path,
    cas_root: Path,
    request_dataset_id: str,
) -> R1ForensicReceipt:
    """Reopen the already-paid data attempts and bind decisive bytes to CAS."""

    journal_path = Path(journal_path)
    cas_root = Path(cas_root)
    terminals = {
        terminal.attempt_id: terminal for terminal in resolve_live_attempt_terminals(journal_path)
    }
    records = _canonical_journal_projection(journal_path)
    metadata_cutoffs = tuple(
        ref.sequence
        for ref, event, _payload in records
        if event.get("event_kind") == "request"
        and isinstance(event.get("request"), Mapping)
        and event["request"].get("call_class") == "indicator_metadata"
    )
    cutoff = min(metadata_cutoffs, default=10**18)
    request_records = tuple(
        (ref, event)
        for ref, event, _payload in records
        if ref.sequence < cutoff
        and event.get("event_kind") == "request"
        and isinstance(event.get("request"), Mapping)
        and event["request"].get("request_dataset_id") == request_dataset_id
        and event["request"].get("call_class", "data_fetch") == "data_fetch"
    )
    if not request_records:
        raise AcquisitionSelectionError("r1_data_attempt_denominator_empty", request_dataset_id)
    terminal_event_by_attempt = {
        str(event.get("attempt_id")): (ref, event)
        for ref, event, _payload in records
        if event.get("event_kind") == "live_attempt_terminal"
    }
    projections: list[R1AttemptForensicProjection] = []
    classified_bodies: list[tuple[str, bytes, WorldBankDataResponseClassification]] = []
    terminal_end_offsets: list[int] = []
    for request_ref, request_event in request_records:
        attempt_id = str(request_event.get("attempt_id") or "")
        terminal = terminals.get(attempt_id)
        terminal_event = terminal_event_by_attempt.get(attempt_id)
        if terminal is None or terminal_event is None:
            raise AcquisitionSelectionError("r1_attempt_terminal_unresolved", attempt_id)
        terminal_ref, terminal_payload = terminal_event
        terminal_end_offsets.append(terminal_ref.byte_offset + terminal_ref.byte_length)
        heartbeat_elapsed = tuple(
            float(event["heartbeat"]["elapsed_seconds"])
            for _ref, event, _payload in records
            if event.get("attempt_id") == attempt_id
            and event.get("event_kind") == "heartbeat"
            and isinstance(event.get("heartbeat"), Mapping)
            and isinstance(event["heartbeat"].get("elapsed_seconds"), (int, float))
            and not isinstance(event["heartbeat"].get("elapsed_seconds"), bool)
        )
        raw_body: bytes | None = None
        raw_body_sha: str | None = None
        raw_byte_count: int | None = None
        if terminal.raw_evidence_ref is not None:
            raw_body = resolve_raw_response_body(terminal.raw_evidence_ref)
            raw_body_sha = f"sha256:{hashlib.sha256(raw_body).hexdigest()}"
            raw_byte_count = len(raw_body)
            classified_bodies.append(
                (attempt_id, raw_body, classify_worldbank_data_response(raw_body))
            )
        values: dict[str, object] = {
            "attempt_id": attempt_id,
            "request_sequence": request_ref.sequence,
            "request_event_sha256": request_ref.event_sha256,
            "request_dataset_id": request_dataset_id,
            "terminal_event_sha256": terminal_ref.event_sha256,
            "terminal_sha256": terminal.terminal_sha256,
            "terminal_outcome": terminal.outcome_code,
            "terminal_failure_code": terminal.failure_code,
            "raw_evidence_event_sha256": (
                terminal.raw_evidence_ref.event_sha256
                if terminal.raw_evidence_ref is not None
                else None
            ),
            "raw_body_sha256": raw_body_sha,
            "raw_byte_count": raw_byte_count,
            "http_status_code": terminal.http_status_code,
            "max_elapsed_seconds": max(heartbeat_elapsed, default=0.0),
        }
        projections.append(
            R1AttemptForensicProjection(
                **values,
                projection_sha256=content_sha256(values),
            )
        )
        if terminal_payload.get("terminal_sha256") != terminal.terminal_sha256:
            raise AcquisitionSelectionError("r1_terminal_projection_drift", attempt_id)
    decisive = tuple(
        item
        for item in classified_bodies
        if item[2].disposition is CarrierDataDisposition.NO_DATA_FOR_SCOPE
    )
    if len(decisive) != 1:
        raise AcquisitionSelectionError(
            "r1_decisive_response_unresolved",
            f"{request_dataset_id}:{len(decisive)}",
        )
    decisive_attempt_id, decisive_body, classification = decisive[0]
    if not cas_root.is_dir():
        raise AcquisitionSelectionError("r1_cas_unresolved", cas_root.as_posix())
    artifact_id = ArtifactID.model_validate(classification.body_sha256)
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    cas_body = store.get_bytes(artifact_id)
    if cas_body != decisive_body:
        raise AcquisitionSelectionError("r1_cas_body_drift", classification.body_sha256)
    blob_path, manifest_path = store.get_paths(artifact_id)
    prefix_length = max(terminal_end_offsets)
    prefix = journal_path.read_bytes()[:prefix_length]
    values = {
        "schema_version": "policyos.layer3.gy.n13b.r1_forensics.v1",
        "journal_ref": _stable_repo_ref(journal_path),
        "journal_prefix_byte_length": prefix_length,
        "journal_prefix_sha256": f"sha256:{hashlib.sha256(prefix).hexdigest()}",
        "cas_blob_ref": _stable_repo_ref(blob_path),
        "cas_manifest_ref": _stable_repo_ref(manifest_path),
        "cas_blob_sha256": classification.body_sha256,
        "request_dataset_id": request_dataset_id,
        "attempts": tuple(projections),
        "decisive_attempt_id": decisive_attempt_id,
        "classification": classification,
    }
    return R1ForensicReceipt(
        **values,
        receipt_sha256=content_sha256(values),
    )


def derive_metadata_probe_owner(
    *,
    r1_receipt: R1ForensicReceipt,
    baseline_path: Path,
    fixture_root: Path,
) -> MetadataProbeOwner:
    """Derive exact E7/E5 authorization for the one R2 metadata call."""

    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    r1 = R1ForensicReceipt.model_validate(r1_receipt.model_dump(mode="python"))
    baseline_path = Path(baseline_path)
    if not baseline_path.is_file():
        raise AcquisitionSelectionError("metadata_baseline_unresolved", baseline_path.as_posix())
    baseline_sha = bytes_sha256(baseline_path.read_bytes())
    profile_id = "worldbank_wdi"
    profile = SourceProfileRegistry.get_instance().get(profile_id)
    if profile is None or str(profile.connector_family) != "worldbank":
        raise AcquisitionSelectionError("metadata_source_profile_unresolved", profile_id)
    attempt_prefix = r1.decisive_attempt_id.rsplit("-", 1)[0]
    attempt_id = f"{attempt_prefix}-metadata-001"
    harness = derive_worldbank_metadata_harness_receipt(
        attempt_id=attempt_id,
        indicator_id=r1.request_dataset_id,
        profile_id=profile_id,
        fixture_root=fixture_root,
    )
    schema_contract = {
        "schema_contract_ref": "fabric://worldbank.wdi.indicator_metadata@1.0.0",
        "call_class": "indicator_metadata",
        "expected_envelope": "worldbank_indicator_metadata",
        "declared_record_fields": ["id", "name", "source", "unit"],
        "conformance_stage": "quarantine_characterization",
    }
    request: dict[str, Any] = {
        "call_class": "indicator_metadata",
        "connector_id": "worldbank.wdi",
        "profile_id": profile_id,
        "variable_id": r1.request_dataset_id,
        "request_variables": [r1.request_dataset_id],
        "endpoint_url": harness.endpoint_url,
        "params": harness.params,
        "schema_contract": schema_contract,
        "source_lane": "shadow_characterization",
        "response_admitted": False,
    }
    decisive_attempt = next(
        attempt for attempt in r1.attempts if attempt.attempt_id == r1.decisive_attempt_id
    )
    authorization = build_live_metadata_execution_authorization(
        request=request,
        schema_contract=schema_contract,
        source_profile=profile,
        baseline_sha256=baseline_sha,
        harness_receipt=harness,
        paid_success_elapsed_seconds=decisive_attempt.max_elapsed_seconds,
        timeout_multiplier=2,
        heartbeat_cap_seconds=3.0,
        max_response_bytes=16_384,
        max_decompressed_bytes=16_384,
    )
    values: dict[str, object] = {
        "schema_version": "policyos.layer3.gy.n13b.metadata_probe_owner.v1",
        "r1_receipt_sha256": r1.receipt_sha256,
        "baseline_ref": _stable_repo_ref(baseline_path),
        "baseline_sha256": baseline_sha,
        "request": request,
        "harness": harness,
        "authorization": authorization,
    }
    return MetadataProbeOwner(
        **values,
        owner_sha256=content_sha256(values),
    )


def derive_metadata_probe_execution_evidence(
    *,
    owner: MetadataProbeOwner,
    r1_receipt: R1ForensicReceipt,
    journal_path: Path,
    cas_root: Path,
    baseline_path: Path,
) -> tuple[MetadataProbeExecutionEvidence, object]:
    """Reopen R2 evidence and derive its N13a D3 carrier update."""

    from tools.quality.validation import layer3_gy_n13a_acquisition_census as census

    owner = MetadataProbeOwner.model_validate(owner.model_dump(mode="python"))
    r1 = R1ForensicReceipt.model_validate(r1_receipt.model_dump(mode="python"))
    if owner.r1_receipt_sha256 != r1.receipt_sha256:
        raise AcquisitionSelectionError("metadata_r1_receipt_drift", owner.owner_sha256)
    baseline_path = Path(baseline_path)
    baseline_sha = bytes_sha256(baseline_path.read_bytes())
    if baseline_sha != owner.baseline_sha256:
        raise AcquisitionSelectionError("metadata_baseline_mutation", baseline_path.as_posix())
    records = _canonical_journal_projection(Path(journal_path))
    attempt_id = owner.authorization.attempt_id
    terminals = {
        terminal.attempt_id: terminal
        for terminal in resolve_live_attempt_terminals(Path(journal_path))
    }
    terminal = terminals.get(attempt_id)
    if terminal is None:
        raise AcquisitionSelectionError("metadata_attempt_terminal_unresolved", attempt_id)
    request_events = tuple(
        (ref, event)
        for ref, event, _payload in records
        if event.get("event_kind") == "request" and event.get("attempt_id") == attempt_id
    )
    if len(request_events) != 1:
        raise AcquisitionSelectionError("metadata_request_unresolved", attempt_id)
    request_ref, request_event = request_events[0]
    if (
        request_event.get("request") != owner.request
        or request_event.get("request_sha256") != content_sha256(owner.request)
        or request_ref != terminal.request_ref
    ):
        raise AcquisitionSelectionError("metadata_request_projection_drift", attempt_id)
    heartbeat_elapsed = tuple(
        float(event["heartbeat"]["elapsed_seconds"])
        for _ref, event, _payload in records
        if event.get("event_kind") == "heartbeat"
        and event.get("attempt_id") == attempt_id
        and isinstance(event.get("heartbeat"), Mapping)
        and isinstance(event["heartbeat"].get("elapsed_seconds"), (int, float))
        and not isinstance(event["heartbeat"].get("elapsed_seconds"), bool)
    )
    call_count = sum(
        event.get("event_kind") == "transport_attempt" and event.get("attempt_id") == attempt_id
        for _ref, event, _payload in records
    )
    if call_count > 1:
        raise AcquisitionSelectionError("metadata_call_budget_exceeded", attempt_id)
    raw_ref = terminal.raw_evidence_ref
    classification: WorldBankIndicatorMetadataClassification | None = None
    transport_trace: LiveTransportTrace | None = None
    raw_body: bytes | None = None
    raw_body_sha: str | None = None
    raw_byte_count: int | None = None
    raw_artifact_id: str | None = None
    store = FileSystemCAS(Path(cas_root), ownership_enforced=False)
    if raw_ref is not None:
        raw_body = resolve_raw_response_body(raw_ref)
        classification = classify_worldbank_indicator_metadata(
            raw_body,
            indicator_id=r1.request_dataset_id,
        )
        classification_events = tuple(
            event
            for _ref, event, _payload in records
            if event.get("event_kind") == "classification" and event.get("attempt_id") == attempt_id
        )
        if (
            len(classification_events) != 1
            or classification_events[0].get("evidence_event_sha256") != raw_ref.event_sha256
            or classification_events[0].get("classification")
            != classification.model_dump(mode="json")
        ):
            raise AcquisitionSelectionError("metadata_classification_drift", attempt_id)
        raw_body_sha = classification.body_sha256
        raw_byte_count = len(raw_body)
        raw_artifact_id = raw_body_sha
        if store.get_bytes(ArtifactID.model_validate(raw_artifact_id)) != raw_body:
            raise AcquisitionSelectionError("metadata_cas_body_drift", attempt_id)
        transport_trace = resolve_live_transport_trace(raw_ref)
    elif any(
        event.get("event_kind") == "classification" and event.get("attempt_id") == attempt_id
        for _ref, event, _payload in records
    ):
        raise AcquisitionSelectionError("metadata_classification_without_raw", attempt_id)
    values: dict[str, object] = {
        "schema_version": "policyos.layer3.gy.n13b.metadata_probe_evidence.v1",
        "owner_sha256": owner.owner_sha256,
        "attempt_id": attempt_id,
        "baseline_before_sha256": owner.baseline_sha256,
        "baseline_after_sha256": baseline_sha,
        "request_ref": request_ref,
        "raw_evidence_ref": raw_ref,
        "raw_artifact_id": raw_artifact_id,
        "raw_body_sha256": raw_body_sha,
        "raw_byte_count": raw_byte_count,
        "classification": classification,
        "transport_trace": transport_trace,
        "terminal": terminal,
        "call_count": call_count,
        "quarantine": True,
        "response_admitted": False,
    }
    execution_evidence = MetadataProbeExecutionEvidence(
        **values,
        evidence_sha256=content_sha256(values),
    )
    data_attempts = tuple(
        census.RecurringCarrierAttemptEvidence(
            attempt_id=attempt.attempt_id,
            call_class="data_fetch",
            request_dataset_id=attempt.request_dataset_id,
            request_event_sha256=attempt.request_event_sha256,
            raw_evidence_event_sha256=attempt.raw_evidence_event_sha256,
            terminal_sha256=attempt.terminal_sha256,
            terminal_outcome=attempt.terminal_outcome,
            raw_body_sha256=attempt.raw_body_sha256,
            http_status_code=attempt.http_status_code,
            max_elapsed_seconds=attempt.max_elapsed_seconds,
        )
        for attempt in r1.attempts
    )
    metadata_attempt = census.RecurringCarrierAttemptEvidence(
        attempt_id=attempt_id,
        call_class="indicator_metadata",
        request_dataset_id=r1.request_dataset_id,
        request_event_sha256=request_ref.event_sha256,
        raw_evidence_event_sha256=(raw_ref.event_sha256 if raw_ref is not None else None),
        terminal_sha256=terminal.terminal_sha256,
        terminal_outcome=terminal.outcome_code,
        raw_body_sha256=raw_body_sha,
        http_status_code=terminal.http_status_code,
        max_elapsed_seconds=max(heartbeat_elapsed, default=0.0),
    )
    with duckdb.connect(str(baseline_path), read_only=True) as connection:
        carrier_owner_rows = tuple(
            connection.execute(
                """
                SELECT binding.execution_tier,
                       dataset.themes,
                       distribution.connector_params,
                       binding.default_filters
                FROM ds_metric_bindings AS binding
                JOIN ds_datasets AS dataset ON dataset.id = binding.dataset_id
                JOIN ds_distributions AS distribution
                  ON distribution.id = binding.distribution_id
                WHERE binding.connector_id = ? AND binding.request_dataset_id = ?
                ORDER BY binding.dataset_id, binding.distribution_id
                """,
                [owner.request["connector_id"], r1.request_dataset_id],
            ).fetchall()
        )
    tiers = tuple(sorted({str(row[0]) for row in carrier_owner_rows}))
    if len(tiers) != 1:
        raise AcquisitionSelectionError(
            "metadata_execution_tier_unresolved",
            f"{r1.request_dataset_id}:{tiers}",
        )
    catalog_source_names = tuple(
        sorted(
            {
                str(value).strip()
                for _tier, themes, _params, _filters in carrier_owner_rows
                for value in _string_values(themes)
                if str(value).strip()
            }
        )
    )
    source_selector_declared = any(
        any(key in {"source", "source_id"} for key in _mapping_keys(value))
        for _tier, _themes, params, filters in carrier_owner_rows
        for value in (params, filters)
    )
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    profile = SourceProfileRegistry.get_instance().get(owner.authorization.profile_id)
    if profile is None:
        raise AcquisitionSelectionError(
            "metadata_source_profile_unresolved",
            owner.authorization.profile_id,
        )
    profile_source_descriptors = tuple(
        sorted(
            {
                str(value).strip()
                for value in (profile.display_name, profile.description)
                if str(value).strip()
            }
        )
    )
    decisive_body = store.get_bytes(ArtifactID.model_validate(r1.cas_blob_sha256))
    carrier_update = census.derive_recurring_carrier_liveness_update(
        connector_id=str(owner.request["connector_id"]),
        request_dataset_id=r1.request_dataset_id,
        execution_tier=tiers[0],
        data_attempts=data_attempts,
        decisive_data_body=decisive_body,
        metadata_attempt=metadata_attempt,
        metadata_body=raw_body,
        catalog_source_names=catalog_source_names,
        profile_source_descriptors=profile_source_descriptors,
        source_selector_declared=source_selector_declared,
    )
    return execution_evidence, carrier_update


def _canonical_journal_projection(
    journal_path: Path,
) -> tuple[tuple[JournalEventRef, dict[str, Any], bytes], ...]:
    payloads = journal_path.read_bytes().splitlines(keepends=True)
    if not payloads or b"".join(payloads) != journal_path.read_bytes():
        raise AcquisitionSelectionError("r1_journal_not_canonical", journal_path.as_posix())
    records: list[tuple[JournalEventRef, dict[str, Any], bytes]] = []
    offset = 0
    for expected_sequence, payload in enumerate(payloads, start=1):
        try:
            event = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcquisitionSelectionError(
                "r1_journal_not_canonical",
                journal_path.as_posix(),
            ) from exc
        if (
            not isinstance(event, dict)
            or event.get("sequence") != expected_sequence
            or canonical_json_bytes(event) != payload
            or not isinstance(event.get("event_kind"), str)
        ):
            raise AcquisitionSelectionError(
                "r1_journal_not_canonical",
                journal_path.as_posix(),
            )
        ref = JournalEventRef(
            journal_path=journal_path.as_posix(),
            sequence=expected_sequence,
            event_kind=str(event["event_kind"]),
            event_sha256=f"sha256:{hashlib.sha256(payload).hexdigest()}",
            byte_offset=offset,
            byte_length=len(payload),
        )
        resolve_journal_event_ref(ref)
        records.append((ref, event, payload))
        offset += len(payload)
    return tuple(records)


def _stable_repo_ref(path: Path) -> str:
    resolved = Path(path).resolve()
    policy_root = Path(__file__).resolve().parents[3]
    try:
        relative = resolved.relative_to(policy_root)
    except ValueError:
        parts = resolved.parts
        policy_indexes = tuple(index for index, part in enumerate(parts) if part == "policy-engine")
        if policy_indexes:
            candidate = Path(*parts[policy_indexes[-1] + 1 :])
            if candidate.parts and candidate.parts[0] == "production_data":
                return f"repo://{candidate.as_posix()}"
        return resolved.as_posix()
    return f"repo://{relative.as_posix()}"


def derive_worldbank_metadata_harness_receipt(
    *,
    attempt_id: str,
    indicator_id: str,
    profile_id: str,
    fixture_root: Path,
) -> LiveMetadataHarnessReceipt:
    """Exercise the exact metadata method under REPLAY with zero network escape."""

    return asyncio.run(
        _derive_worldbank_metadata_harness_receipt_async(
            attempt_id=attempt_id,
            indicator_id=indicator_id,
            profile_id=profile_id,
            fixture_root=fixture_root,
        )
    )


async def _derive_worldbank_metadata_harness_receipt_async(
    *,
    attempt_id: str,
    indicator_id: str,
    profile_id: str,
    fixture_root: Path,
) -> LiveMetadataHarnessReceipt:
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
    from polisyos.fabric.connectors.testing.simulator import (
        APISimulator,
        MissingFixtureError,
        SimulatorMode,
    )

    profile = SourceProfileRegistry.get_instance().get(profile_id)
    if profile is None or str(profile.connector_family) != "worldbank":
        raise AcquisitionSelectionError("metadata_source_profile_unresolved", profile_id)
    connector = WorldBankConnector()
    config = resolve_connection_config(profile)
    endpoint = f"{profile.base_url.rstrip('/')}/indicator/{indicator_id}"
    params = {"format": "json", "page": "1", "per_page": "1"}
    simulator = APISimulator(
        mode=SimulatorMode.REPLAY,
        fixture_root=Path(fixture_root),
        connector_id=connector.connector_id,
        dataset_id=f"indicator-metadata-{indicator_id}",
        max_call_log_entries=10,
    )
    blocked_escapes: list[str] = []
    captured: BaseException | None = None
    completed = False

    def block_network(*_: Any, **__: Any) -> None:
        blocked_escapes.append(attempt_id)
        raise AcquisitionSelectionError("metadata_harness_network_escape", attempt_id)

    handle: Any | None = None
    with (
        patch.object(socket.socket, "connect", new=block_network),
        patch.object(socket.socket, "connect_ex", new=block_network),
        patch.object(socket, "create_connection", new=block_network),
    ):
        try:
            handle = await connector.connect(config)
            async with simulator:
                await connector.fetch_indicator_metadata_raw(handle, indicator_id)
            completed = True
        except BaseException as exc:  # noqa: BLE001 - typed E7 boundary
            captured = exc
        finally:
            if handle is not None:
                try:
                    await connector.disconnect(handle)
                except BaseException as exc:  # noqa: BLE001 - typed E7 boundary
                    if captured is None:
                        captured = exc
    intercepted = simulator.call_count > 0
    if blocked_escapes:
        outcome = "network_escape_blocked"
    elif completed and intercepted:
        outcome = "metadata_result_validated"
    elif isinstance(captured, MissingFixtureError) and intercepted:
        outcome = "replay_fixture_missing_after_interception"
    elif intercepted:
        outcome = "intercepted_response_rejected"
    else:
        outcome = "pretransport_rejected"
    values: dict[str, object] = {
        "schema_version": "polisyos.fabric.live_metadata_harness_receipt.v1",
        "attempt_id": attempt_id,
        "connector_id": connector.connector_id,
        "profile_id": profile_id,
        "request_variable": indicator_id,
        "call_class": "indicator_metadata",
        "endpoint_url": endpoint,
        "params": params,
        "simulator_mode": "replay",
        "simulator_call_count": simulator.call_count,
        "transport_intercepted": intercepted,
        "network_escape_attempt_count": len(blocked_escapes),
        "actual_network_call_count": 0,
        "outcome": outcome,
        "safe_dry_run_passed": (
            simulator.call_count == 1
            and intercepted
            and not blocked_escapes
            and outcome
            in {
                "metadata_result_validated",
                "replay_fixture_missing_after_interception",
            }
        ),
    }
    return LiveMetadataHarnessReceipt(
        **values,
        receipt_sha256=content_sha256(values),
    )


def _worldbank_api_messages(payload: object) -> tuple[object, ...]:
    containers: list[object] = []
    if isinstance(payload, Mapping):
        containers.append(payload.get("message"))
    elif isinstance(payload, list) and payload and isinstance(payload[0], Mapping):
        containers.append(payload[0].get("message"))
    messages: list[object] = []
    for value in containers:
        if isinstance(value, list):
            messages.extend(value)
        elif value is not None:
            messages.append(value)
    return tuple(messages)


def _nonbool_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_owner_string(
    record: Mapping[str, object] | None,
    *keys: str,
) -> str | None:
    if record is None:
        return None
    for key in keys:
        value = _optional_string(record.get(key))
        if value is not None:
            return value
    return None


def _string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(str(item) for item in value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return (value,)
        if isinstance(decoded, Sequence) and not isinstance(
            decoded,
            (str, bytes, bytearray),
        ):
            return tuple(str(item) for item in decoded)
        return (str(decoded),)
    return ()


def _mapping_keys(value: object) -> frozenset[str]:
    decoded = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return frozenset()
    if not isinstance(decoded, Mapping):
        return frozenset()
    return frozenset(str(key).strip().casefold() for key in decoded)


@dataclass(frozen=True)
class TargetAuthorityOwners:
    """Byte-stable owner artifacts required before the selected live call."""

    selection: LiveTargetSelection
    entry: Any
    registry: Any
    provision: Any
    family_receipt: Any
    family_receipt_bytes: bytes
    additional_family_receipts: tuple[Any, ...]
    additional_family_receipt_payloads: tuple[tuple[Path, bytes], ...]
    registry_bytes: bytes
    provision_bytes: bytes

    def payloads(self) -> dict[Path, bytes]:
        """Return canonical repository-relative owner payloads."""

        payloads = {
            DEFAULT_TARGET_AUTHORITY_REGISTRY: self.registry_bytes,
            DEFAULT_TARGET_AUTHORITY_PROVISION: self.provision_bytes,
            DEFAULT_TARGET_HARNESS_RECEIPT: self.family_receipt_bytes,
        }
        payloads.update(dict(self.additional_family_receipt_payloads))
        return payloads


class LiveTargetSelection(_StrictModel):
    """One target selected from complete source denominators and owner evidence."""

    schema_version: Literal["policyos.layer3.gy.n13b.live_target_selection.v1"] = (
        TARGET_SELECTION_SCHEMA_VERSION
    )
    selection_content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    target_variable: str = Field(min_length=1)
    canonical_unit: str = Field(min_length=1)
    backlog_rank: int = Field(ge=1)
    demand_sources: tuple[str, ...] = Field(min_length=1)
    live_family_denominator: tuple[str, ...] = Field(min_length=1)
    eligible_target_denominator: tuple[str, ...] = Field(min_length=1)
    catalog_candidate_denominator: int = Field(ge=1)
    eligible_catalog_candidate_count: int = Field(ge=1)
    rejected_candidate_counts: dict[str, int]
    source_catalog_dataset_id: str = Field(min_length=1)
    source_catalog_distribution_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    upstream_metric_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    agency: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    access_license: str = Field(min_length=1)
    execution_tier: Literal["fetchable", "transport_ready"]
    binding_confidence: float = Field(ge=0.0, le=1.0)
    distribution_quality_score: float = Field(ge=0.0, le=1.0)
    temporal_start: str | None = None
    temporal_end: str | None = None
    alignment_score: VariablePairAlignmentScore

    @model_validator(mode="after")
    def _selection_is_recomputed(self) -> Self:
        if self.demand_sources != tuple(sorted(set(self.demand_sources))):
            raise ValueError("demand sources must be unique and sorted")
        if self.live_family_denominator != tuple(sorted(set(self.live_family_denominator))):
            raise ValueError("live family denominator must be unique and sorted")
        if self.eligible_target_denominator != tuple(sorted(set(self.eligible_target_denominator))):
            raise ValueError("eligible target denominator must be unique and sorted")
        if self.target_variable not in self.eligible_target_denominator:
            raise ValueError("selected target must belong to the eligible denominator")
        if self.connector_id not in self.live_family_denominator:
            raise ValueError("selected connector must belong to the live denominator")
        if any(count < 0 for count in self.rejected_candidate_counts.values()):
            raise ValueError("rejected candidate counts must be nonnegative")
        if (
            self.eligible_catalog_candidate_count + sum(self.rejected_candidate_counts.values())
            != self.catalog_candidate_denominator
        ):
            raise ValueError("candidate outcomes must cover the complete denominator")
        owner_unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(
            f"{self.title} {self.description}"
        )
        if owner_unit != self.canonical_unit:
            raise ValueError("selected catalog unit must match the demanded owner unit")
        expected_score = data_forge_read_api.catalog.score_variable_pair(
            left_name=self.target_variable,
            right_name=self.upstream_metric_id,
            left_unit=self.canonical_unit,
            right_unit=owner_unit,
        )
        if self.alignment_score != expected_score:
            raise ValueError("alignment score must be recomputed by its owner")
        if self.selection_content_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("selection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the source-evidence projection defining target selection."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "selection_content_sha256"
        }


def derive_live_target_selection(
    *,
    catalog_path: Path,
    census_path: Path,
    substrate_path: Path,
) -> LiveTargetSelection:
    """Select one honest live carrier from the full evidence-derived denominator."""

    census = _read_mapping(census_path, code="n13a_census")
    substrate = _read_mapping(substrate_path, code="intervention_substrate")
    backlog = _growth_backlog(census)
    live_families = _live_family_denominator(census)
    owner_units = _slot_units(substrate)
    eligible_targets = tuple(
        sorted(
            variable_id
            for variable_id, row in backlog.items()
            if row["gap_kind"] == "binding_gap" and len(owner_units.get(variable_id, ())) == 1
        )
    )
    if not eligible_targets:
        raise AcquisitionSelectionError("live_target_owner_unit_denominator_empty")

    rows = _read_catalog_candidates(
        Path(catalog_path),
        live_families=live_families,
    )
    if not rows:
        raise AcquisitionSelectionError("live_catalog_candidate_denominator_empty")
    rejected: Counter[str] = Counter()
    ranked: list[tuple[tuple[object, ...], dict[str, object]]] = []
    for target_variable in eligible_targets:
        units = owner_units[target_variable]
        canonical_unit = units[0]
        for row in rows:
            catalog_unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(
                f"{row['title']} {row['description']}"
            )
            if catalog_unit is None:
                rejected["catalog_unit_unresolved"] += 1
                continue
            if catalog_unit != canonical_unit:
                rejected["unit_mismatch"] += 1
                continue
            if (
                data_forge_read_api.catalog.derive_license_disposition(
                    str(row["access_license"])
                ).value
                != "admissible_open"
            ):
                rejected["license_not_admissible"] += 1
                continue
            if bool(row["access_auth_required"]):
                rejected["auth_required"] += 1
                continue
            if not bool(row["parser_supported"]):
                rejected["parser_unsupported"] += 1
                continue
            score = data_forge_read_api.catalog.score_variable_pair(
                left_name=target_variable,
                right_name=str(row["upstream_metric_id"]),
                left_unit=canonical_unit,
                right_unit=catalog_unit,
            )
            rank_key = (
                int(backlog[target_variable]["rank"]),
                -score.overall_score,
                -float(row["binding_confidence"]),
                -float(row["distribution_quality_score"]),
                str(row["source_catalog_dataset_id"]),
                str(row["source_catalog_distribution_id"]),
                str(row["request_dataset_id"]),
                str(row["upstream_metric_id"]),
            )
            ranked.append(
                (
                    rank_key,
                    {
                        **row,
                        "target_variable": target_variable,
                        "canonical_unit": canonical_unit,
                        "alignment_score": score,
                    },
                )
            )
    if not ranked:
        raise AcquisitionSelectionError(
            "live_catalog_candidate_not_admissible",
            json.dumps(dict(sorted(rejected.items())), sort_keys=True),
        )

    selected = min(ranked, key=lambda item: item[0])[1]
    target_variable = str(selected["target_variable"])
    backlog_row = backlog[target_variable]
    values: dict[str, object] = {
        "target_variable": target_variable,
        "canonical_unit": selected["canonical_unit"],
        "backlog_rank": backlog_row["rank"],
        "demand_sources": backlog_row["demand_sources"],
        "live_family_denominator": live_families,
        "eligible_target_denominator": eligible_targets,
        "catalog_candidate_denominator": len(rows) * len(eligible_targets),
        "eligible_catalog_candidate_count": len(ranked),
        "rejected_candidate_counts": dict(sorted(rejected.items())),
        "source_catalog_dataset_id": selected["source_catalog_dataset_id"],
        "source_catalog_distribution_id": selected["source_catalog_distribution_id"],
        "connector_id": selected["connector_id"],
        "profile_id": selected["profile_id"],
        "request_dataset_id": selected["request_dataset_id"],
        "upstream_metric_id": selected["upstream_metric_id"],
        "source": selected["source"],
        "agency": selected["agency"],
        "source_locator": selected["source_locator"],
        "title": selected["title"],
        "description": selected["description"],
        "access_license": selected["access_license"],
        "execution_tier": selected["execution_tier"],
        "binding_confidence": selected["binding_confidence"],
        "distribution_quality_score": selected["distribution_quality_score"],
        "temporal_start": selected["temporal_start"],
        "temporal_end": selected["temporal_end"],
        "alignment_score": selected["alignment_score"],
    }
    provisional = LiveTargetSelection.model_construct(
        **values,
        selection_content_sha256="sha256:" + "0" * 64,
    )
    return LiveTargetSelection(
        **values,
        selection_content_sha256=content_sha256(provisional.identity_payload()),
    )


def build_selected_live_authority_entry(
    selection: LiveTargetSelection,
    *,
    l5_family_id: str,
    country_codes: tuple[str, ...],
) -> Any:
    """Build the last-mile registry edge from selection and connector schema owners."""

    selected = LiveTargetSelection.model_validate(selection.model_dump(mode="python"))
    if selected.connector_id != "worldbank.wdi":
        raise AcquisitionSelectionError(
            "live_connector_schema_owner_unimplemented",
            selected.connector_id,
        )
    value_fields = tuple(
        field
        for field in WDI_GENERIC_SCHEMA.fields
        if field.name not in WDI_GENERIC_SCHEMA.primary_key and field.additivity is not None
    )
    if len(value_fields) != 1:
        raise AcquisitionSelectionError("connector_value_field_ambiguous")
    raw_field = value_fields[0].name
    schema_columns = tuple(
        sorted(
            (
                data_forge_read_api.catalog.AuthoritySchemaColumn(
                    name=field.name,
                    logical_types=(field.data_type.value,),
                    nullable=field.nullable,
                )
                for field in WDI_GENERIC_SCHEMA.fields
            ),
            key=lambda field: field.name,
        )
    )
    landing_suffix = selected.selection_content_sha256.removeprefix("sha256:")[:20]
    evidence_refs = (
        f"repo://architecture/policy_design_case/"
        f"layer3_gy_n13a_acquisition_census.json#/growth_backlog/{selected.backlog_rank - 1}",
        "repo://architecture/policy_design_case/"
        "layer3_gy_intervention_substrate_contract.json#slot/"
        f"{selected.target_variable}",
        "repo://production_data/datasets_full_phase3full_20260327_183054/"
        "dataset_catalog.duckdb#ds_metric_bindings/"
        f"{selected.source_catalog_dataset_id}/{selected.source_catalog_distribution_id}/"
        f"{selected.upstream_metric_id}",
        "python://polisyos.data_forge.domains.catalog.knowledge.variable_alignment/"
        "score_variable_pair",
    )
    return data_forge_read_api.catalog.build_authority_entry(
        source_lane="live_fetch",
        target_variable=selected.target_variable,
        landing_dataset_id=f"acquisition.live.{landing_suffix}",
        landing_distribution_id=f"acquisition.live.{landing_suffix}.wdi",
        source_catalog_dataset_id=selected.source_catalog_dataset_id,
        source_catalog_distribution_id=selected.source_catalog_distribution_id,
        upstream_metric_id=selected.upstream_metric_id,
        catalog_raw_variable=selected.request_dataset_id,
        raw_field=raw_field,
        raw_unit=selected.canonical_unit,
        canonical_unit=selected.canonical_unit,
        unit_transform="identity",
        unit_transform_ref=f"fabric://units/{selected.canonical_unit}-identity/v1",
        alignment_method="semantic",
        alignment_confidence=selected.alignment_score.overall_score,
        is_proxy=False,
        proxy_penalty=0.0,
        aggregation_method="identity",
        valid_min=None,
        valid_max=None,
        evidence_refs=evidence_refs,
        schema_contract_ref=(
            f"fabric://{WDI_GENERIC_SCHEMA.schema_id}@{WDI_GENERIC_SCHEMA.version}"
        ),
        schema_columns=schema_columns,
        l5_family_id=l5_family_id,
        title=f"Acquired {selected.title}",
        description=(
            "Passport-admitted acquisition overlay rows selected from the N13a "
            f"backlog for {selected.target_variable}."
        ),
        country_codes=tuple(sorted(set(country_codes))),
        temporal_start=selected.temporal_start,
        temporal_end=selected.temporal_end,
    )


def derive_live_attempt_id(
    selection: LiveTargetSelection,
    *,
    attempt_ordinal: int = 1,
) -> str:
    """Derive the stable one-variable attempt identity from selected evidence."""

    selected = LiveTargetSelection.model_validate(selection.model_dump(mode="python"))
    if isinstance(attempt_ordinal, bool) or not 1 <= attempt_ordinal <= 999:
        raise AcquisitionSelectionError("live_attempt_ordinal_invalid")
    family = re.sub(r"[^a-z0-9]+", "-", selected.connector_id.casefold()).strip("-")
    target = re.sub(r"[^a-z0-9]+", "-", selected.target_variable.casefold()).strip("-")
    unit = re.sub(r"[^a-z0-9]+", "-", selected.canonical_unit.casefold()).strip("-")
    return f"gy-n13b-{family}-{target}-{unit}-{attempt_ordinal:03d}"


def derive_target_family_receipt(
    selection: LiveTargetSelection,
    *,
    catalog_path: Path,
    fixture_root: Path,
    attempt_ordinal: int = 1,
) -> Any:
    """Run the exact selected carrier through the N13a zero-network E7 owner."""

    from tools.quality.validation import layer3_gy_n13a_acquisition_census as census

    selected = LiveTargetSelection.model_validate(selection.model_dump(mode="python"))
    con = duckdb.connect(str(catalog_path), read_only=True)
    try:
        rows = con.execute(
            """
            SELECT
                b.metric_id,
                b.dataset_id,
                b.distribution_id,
                b.connector_id,
                b.profile_id,
                b.request_dataset_id,
                b.confidence,
                b.default_filters,
                b.execution_tier,
                x.url,
                x.connector_params,
                x.quality_score,
                x.parser_supported,
                d.access_license,
                d.access_auth_required,
                p.columns_json,
                p.sample_row_count,
                p.preview_sample_hash,
                p.inference_mode,
                p.parser_mode
            FROM ds_metric_bindings b
            JOIN ds_datasets d ON d.id = b.dataset_id
            JOIN ds_distributions x
              ON x.id = b.distribution_id AND x.dataset_id = b.dataset_id
             AND x.connector_type = b.connector_id AND x.profile_id = b.profile_id
            LEFT JOIN ds_schema_profiles p
              ON p.distribution_id = b.distribution_id AND p.dataset_id = b.dataset_id
            WHERE b.dataset_id = ? AND b.distribution_id = ?
              AND b.metric_id = ? AND b.request_dataset_id = ?
              AND b.connector_id = ? AND b.profile_id = ?
            """,
            [
                selected.source_catalog_dataset_id,
                selected.source_catalog_distribution_id,
                selected.upstream_metric_id,
                selected.request_dataset_id,
                selected.connector_id,
                selected.profile_id,
            ],
        ).fetchall()
    finally:
        con.close()
    if len(rows) != 1:
        raise AcquisitionSelectionError("target_harness_catalog_edge_unresolved")
    row = rows[0]
    if row[15] is None:
        raise AcquisitionSelectionError("target_harness_schema_profile_missing")
    schema_profile = census.derive_schema_profile_contract(
        distribution_id=str(row[2]),
        dataset_id=str(row[1]),
        profile_id=str(row[4]),
        columns_json=row[15],
        sample_row_count=int(row[16] or 0),
        preview_sample_hash=str(row[17]) if row[17] is not None else None,
        inference_mode=str(row[18] or "metadata_only"),
        parser_mode=str(row[19] or "metadata_only"),
    )
    quality = float(row[11] or 0.0)
    quality_bucket = census.derive_quality_bucket(quality)
    stratum_id = f"{row[8]}:{quality_bucket}"
    candidate = census.ProbeCandidate(
        attempt_id=derive_live_attempt_id(
            selected,
            attempt_ordinal=attempt_ordinal,
        ),
        connector_id=str(row[3]),
        metric_id=str(row[0]),
        dataset_id=str(row[1]),
        distribution_id=str(row[2]),
        profile_id=str(row[4]),
        request_dataset_id=str(row[5]),
        execution_tier=str(row[8]),
        quality_score=quality,
        quality_bucket=quality_bucket,
        binding_confidence=float(row[6] or 0.0),
        endpoint_url=str(row[9] or ""),
        connector_params=_json_object(row[10]),
        filters=_json_string_lists(row[7]),
        access_license=str(row[13] or ""),
        auth_required=bool(row[14]),
        parser_supported=bool(row[12]),
        schema_profile=schema_profile,
        family_sample_rank=1,
        stratum_id=stratum_id,
        stratum_rank=1,
    )
    plan = census.ProbeSelectionPlan(
        family_projection_binding=census.ProjectionBinding(
            projection_id="n13b_selected_live_connector_family",
            source_artifact=(
                "architecture/policy_design_case/"
                "layer3_gy_n13a_acquisition_census.json#family_scorecards"
            ),
            projection_content_sha256=selected.selection_content_sha256,
            projected_item_count=1,
        ),
        target_per_family=1,
        sampling_receipts=(
            census.FamilySamplingReceipt(
                connector_id=selected.connector_id,
                available_distribution_count=1,
                target_probe_count=1,
                selected_probe_count=1,
                stratum_population_counts={stratum_id: 1},
                selected_stratum_counts={stratum_id: 1},
                open_license_available_count=(
                    1
                    if data_forge_read_api.catalog.derive_license_disposition(
                        str(row[13] or "")
                    ).value
                    == "admissible_open"
                    else 0
                ),
                auth_required_available_count=int(bool(row[14])),
                schema_profile_available_count=1,
            ),
        ),
        candidates=(candidate,),
    )
    receipts = census.derive_connector_family_receipts(
        plan,
        fixture_root=fixture_root,
    )
    if len(receipts) != 1:
        raise AcquisitionSelectionError("target_harness_receipt_ambiguous")
    receipt = receipts[0]
    if not receipt.safe_dry_run_passed:
        raise AcquisitionSelectionError("target_harness_dry_run_failed")
    return receipt


def derive_target_authority_owners(
    selection: LiveTargetSelection,
    *,
    family_receipt: object,
    additional_family_receipts: tuple[tuple[int, object], ...] = (),
    baseline_path: Path,
    baseline_owner_ref: str,
    l5_path: Path,
    l5_owner_ref: str,
    receipt_owner_ref: str,
    country_codes: tuple[str, ...],
) -> TargetAuthorityOwners:
    """Derive registry, provision, and exact E7 receipt bytes without live I/O."""

    from tools.quality.validation import layer3_gy_n13a_acquisition_census as census

    selected = LiveTargetSelection.model_validate(selection.model_dump(mode="python"))
    receipt = census.ConnectorFamilyReceipt.model_validate(family_receipt)
    expected_attempt_id = derive_live_attempt_id(selected)
    _validate_target_family_receipt(
        selected,
        receipt,
        attempt_ordinal=1,
    )
    family_receipt_bytes = canonical_json_bytes(receipt.model_dump(mode="json"))
    additional_receipts: list[Any] = []
    additional_payloads: list[tuple[Path, bytes]] = []
    receipt_provisions: list[dict[str, str]] = [
        {
            "entry_id": "",
            "attempt_id": expected_attempt_id,
            "receipt_owner_ref": receipt_owner_ref,
            "receipt_content_sha256": bytes_sha256(family_receipt_bytes),
        }
    ]
    ordinals = tuple(ordinal for ordinal, _ in additional_family_receipts)
    if ordinals != tuple(sorted(set(ordinals))) or any(ordinal <= 1 for ordinal in ordinals):
        raise AcquisitionSelectionError("additional_harness_attempt_ordinals_invalid")
    for ordinal, raw_receipt in additional_family_receipts:
        resolved_receipt = census.ConnectorFamilyReceipt.model_validate(raw_receipt)
        _validate_target_family_receipt(
            selected,
            resolved_receipt,
            attempt_ordinal=ordinal,
        )
        receipt_bytes = canonical_json_bytes(resolved_receipt.model_dump(mode="json"))
        receipt_path = target_harness_receipt_path(ordinal)
        additional_receipts.append(resolved_receipt)
        additional_payloads.append((receipt_path, receipt_bytes))
        receipt_provisions.append(
            {
                "entry_id": "",
                "attempt_id": derive_live_attempt_id(
                    selected,
                    attempt_ordinal=ordinal,
                ),
                "receipt_owner_ref": f"repo://{receipt_path.as_posix()}",
                "receipt_content_sha256": bytes_sha256(receipt_bytes),
            }
        )
    l5_family_id = _derive_l5_family_id(Path(l5_path))
    entry = build_selected_live_authority_entry(
        selected,
        l5_family_id=l5_family_id,
        country_codes=country_codes,
    )
    baseline_sha256 = _file_sha256(Path(baseline_path))
    l5_sha256 = _file_sha256(Path(l5_path))
    registry = data_forge_read_api.catalog.build_authority_registry(
        baseline_content_sha256=baseline_sha256,
        l5_measurement_registry_sha256=l5_sha256,
        entries=(entry,),
    )
    for provision in receipt_provisions:
        provision["entry_id"] = entry.entry_id
    provision = data_forge_read_api.catalog.build_acquisition_authority_provision(
        baseline_owner_ref=baseline_owner_ref,
        baseline_content_sha256=baseline_sha256,
        l5_measurement_registry_owner_ref=l5_owner_ref,
        l5_measurement_registry_content_sha256=l5_sha256,
        live_harness_receipts=tuple(receipt_provisions),
    )
    return TargetAuthorityOwners(
        selection=selected,
        entry=entry,
        registry=registry,
        provision=provision,
        family_receipt=receipt,
        family_receipt_bytes=family_receipt_bytes,
        additional_family_receipts=tuple(additional_receipts),
        additional_family_receipt_payloads=tuple(additional_payloads),
        registry_bytes=canonical_json_bytes(registry.model_dump(mode="json")),
        provision_bytes=canonical_json_bytes(provision.model_dump(mode="json")),
    )


def bytes_sha256(payload: bytes) -> str:
    """Return the raw file identity used by provision receipts."""

    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def target_harness_receipt_path(attempt_ordinal: int) -> Path:
    """Return the canonical receipt path for one exact live attempt."""

    if isinstance(attempt_ordinal, bool) or not 1 <= attempt_ordinal <= 999:
        raise AcquisitionSelectionError("live_attempt_ordinal_invalid")
    if attempt_ordinal == 1:
        return DEFAULT_TARGET_HARNESS_RECEIPT
    return DEFAULT_TARGET_HARNESS_RECEIPT.with_name(
        DEFAULT_TARGET_HARNESS_RECEIPT.stem
        + f"_attempt_{attempt_ordinal:03d}"
        + DEFAULT_TARGET_HARNESS_RECEIPT.suffix
    )


def _validate_target_family_receipt(
    selection: LiveTargetSelection,
    receipt: Any,
    *,
    attempt_ordinal: int,
) -> None:
    expected_attempt_id = derive_live_attempt_id(
        selection,
        attempt_ordinal=attempt_ordinal,
    )
    if (
        receipt.connector_id != selection.connector_id
        or not receipt.safe_dry_run_passed
        or receipt.carrier_denominator != 1
        or len(receipt.dry_run_attempts) != 1
        or receipt.dry_run_attempts[0].attempt_id != expected_attempt_id
        or receipt.dry_run_attempts[0].request_dataset_id != selection.request_dataset_id
    ):
        raise AcquisitionSelectionError("target_harness_owner_projection_drift")


def _read_catalog_candidates(
    catalog_path: Path,
    *,
    live_families: tuple[str, ...],
) -> tuple[dict[str, object], ...]:
    if not catalog_path.is_file():
        raise AcquisitionSelectionError("catalog_missing", catalog_path.as_posix())
    con = duckdb.connect(str(catalog_path), read_only=True)
    try:
        rows = con.execute(
            """
            SELECT
                d.id,
                x.id,
                b.connector_id,
                b.profile_id,
                b.request_dataset_id,
                b.metric_id,
                d.source,
                d.agency,
                COALESCE(x.source_locator, x.url),
                d.title,
                COALESCE(d.description, ''),
                d.access_license,
                d.access_auth_required,
                b.execution_tier,
                b.confidence,
                x.quality_score,
                x.parser_supported,
                d.temporal_start,
                d.temporal_end
            FROM ds_metric_bindings b
            JOIN ds_datasets d ON d.id = b.dataset_id
            JOIN ds_distributions x
              ON x.id = b.distribution_id AND x.dataset_id = b.dataset_id
            WHERE b.connector_id IN (SELECT UNNEST(?))
              AND b.execution_tier IN ('fetchable', 'transport_ready')
              AND x.connector_type = b.connector_id
              AND x.profile_id = b.profile_id
            ORDER BY d.id, x.id, b.metric_id, b.request_dataset_id
            """,
            [list(live_families)],
        ).fetchall()
    except Exception as exc:
        raise AcquisitionSelectionError(
            "catalog_candidate_query_failed",
            type(exc).__name__,
        ) from exc
    finally:
        con.close()

    keys = (
        "source_catalog_dataset_id",
        "source_catalog_distribution_id",
        "connector_id",
        "profile_id",
        "request_dataset_id",
        "upstream_metric_id",
        "source",
        "agency",
        "source_locator",
        "title",
        "description",
        "access_license",
        "access_auth_required",
        "execution_tier",
        "binding_confidence",
        "distribution_quality_score",
        "parser_supported",
        "temporal_start",
        "temporal_end",
    )
    return tuple(dict(zip(keys, raw, strict=True)) for raw in rows)


def _growth_backlog(census: Mapping[str, object]) -> dict[str, dict[str, object]]:
    raw = census.get("growth_backlog")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise AcquisitionSelectionError("growth_backlog_missing")
    rows: dict[str, dict[str, object]] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            raise AcquisitionSelectionError("growth_backlog_row_invalid")
        variable_id = str(item.get("variable_id") or "").strip()
        gap_kind = str(item.get("gap_kind") or "").strip()
        rank = item.get("rank")
        demand_sources = item.get("demand_sources")
        if (
            not variable_id
            or isinstance(rank, bool)
            or not isinstance(rank, int)
            or rank < 1
            or not isinstance(demand_sources, Sequence)
            or isinstance(demand_sources, (str, bytes, bytearray))
        ):
            raise AcquisitionSelectionError("growth_backlog_row_invalid", variable_id)
        normalized_sources = tuple(sorted({str(value) for value in demand_sources if str(value)}))
        if not normalized_sources or variable_id in rows:
            raise AcquisitionSelectionError("growth_backlog_denominator_invalid", variable_id)
        rows[variable_id] = {
            "rank": rank,
            "gap_kind": gap_kind,
            "demand_sources": normalized_sources,
        }
    return rows


def _live_family_denominator(census: Mapping[str, object]) -> tuple[str, ...]:
    raw = census.get("family_scorecards")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise AcquisitionSelectionError("family_scorecards_missing")
    families: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            raise AcquisitionSelectionError("family_scorecard_invalid")
        connector_id = str(item.get("connector_id") or "").strip()
        counts = item.get("liveness_counts")
        if not connector_id or not isinstance(counts, Mapping):
            raise AcquisitionSelectionError("family_scorecard_invalid", connector_id)
        alive_count = sum(
            int(value)
            for key, value in counts.items()
            if str(key).startswith(_ALIVE_LIVENESS_PREFIX)
            and isinstance(value, int)
            and not isinstance(value, bool)
            and value > 0
        )
        if alive_count:
            families.add(connector_id)
    if not families:
        raise AcquisitionSelectionError("live_family_denominator_empty")
    return tuple(sorted(families))


def _slot_units(substrate: Mapping[str, object]) -> dict[str, tuple[str, ...]]:
    units: defaultdict[str, set[str]] = defaultdict(set)

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            slot_id = value.get("slot_id")
            unit = value.get("unit")
            if isinstance(slot_id, str) and slot_id.strip() and isinstance(unit, str):
                normalized = data_forge_read_api.catalog.normalize_acquisition_unit(unit)
                if normalized:
                    units[slot_id.strip()].add(normalized)
            for nested in value.values():
                visit(nested)
        elif isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            for nested in value:
                visit(nested)

    visit(substrate)
    return {key: tuple(sorted(values)) for key, values in sorted(units.items())}


def _json_object(value: object) -> dict[str, object]:
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise AcquisitionSelectionError("target_harness_json_invalid") from exc
    if not isinstance(parsed, Mapping):
        raise AcquisitionSelectionError("target_harness_json_mapping_required")
    return {str(key): item for key, item in parsed.items()}


def _json_string_lists(value: object) -> dict[str, list[str]]:
    parsed = _json_object(value)
    normalized: dict[str, list[str]] = {}
    for key, item in parsed.items():
        if not isinstance(item, Sequence) or isinstance(item, (str, bytes, bytearray)):
            raise AcquisitionSelectionError("target_harness_filter_list_required", key)
        normalized[key] = [str(member) for member in item]
    return normalized


def _derive_l5_family_id(l5_path: Path) -> str:
    l5 = _read_mapping(l5_path, code="l5_measurement_registry")
    coverage = l5.get("coverage_rules")
    if not isinstance(coverage, Mapping):
        raise AcquisitionSelectionError("l5_coverage_rules_missing")
    schema_tags = {str(tag).casefold() for tag in WDI_GENERIC_SCHEMA.tags}
    candidates = tuple(
        sorted(
            str(family_id)
            for family_id in coverage
            if schema_tags
            & {token for token in re.split(r"[^a-z0-9]+", str(family_id).casefold()) if token}
        )
    )
    if len(candidates) != 1:
        raise AcquisitionSelectionError(
            "l5_schema_family_ambiguous",
            ",".join(candidates),
        )
    return candidates[0]


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise AcquisitionSelectionError("owner_file_missing", path.as_posix())
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _read_mapping(path: Path, *, code: str) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise AcquisitionSelectionError(f"{code}_unreadable", type(exc).__name__) from exc
    if not isinstance(value, Mapping):
        raise AcquisitionSelectionError(f"{code}_mapping_required")
    return {str(key): item for key, item in value.items()}


__all__ = [
    "DEFAULT_CARRIER_LIVENESS_UPDATE",
    "DEFAULT_METADATA_EXECUTION_EVIDENCE",
    "DEFAULT_METADATA_PROBE_OWNER",
    "DEFAULT_R1_FORENSIC_RECEIPT",
    "DEFAULT_TARGET_AUTHORITY_PROVISION",
    "DEFAULT_TARGET_AUTHORITY_REGISTRY",
    "DEFAULT_TARGET_HARNESS_RECEIPT",
    "AcquisitionSelectionError",
    "CarrierDataDisposition",
    "IndicatorMetadataDisposition",
    "LiveTargetSelection",
    "MetadataProbeExecutionEvidence",
    "MetadataProbeOwner",
    "R1AttemptForensicProjection",
    "R1ForensicReceipt",
    "TargetAuthorityOwners",
    "build_selected_live_authority_entry",
    "bytes_sha256",
    "classify_worldbank_data_response",
    "classify_worldbank_indicator_metadata",
    "derive_live_attempt_id",
    "derive_live_target_selection",
    "derive_metadata_probe_execution_evidence",
    "derive_metadata_probe_owner",
    "derive_r1_forensic_receipt",
    "derive_target_authority_owners",
    "derive_target_family_receipt",
    "derive_worldbank_metadata_harness_receipt",
    "target_harness_receipt_path",
]
