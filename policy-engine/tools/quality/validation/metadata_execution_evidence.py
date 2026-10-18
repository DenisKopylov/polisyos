"""Journal-reopened metadata execution evidence owners."""

from __future__ import annotations

import asyncio
import json
import re
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Self
from unittest.mock import patch

import duckdb
from pydantic import Field, model_validator

from polisyos.core.artifacts import ArtifactID, FileSystemCAS
from polisyos.fabric.data_plane import (
    EvidenceJournalError,
    JournalEventRef,
    LiveAttemptTerminal,
    LiveMetadataExecutionAuthorization,
    LiveMetadataHarnessReceipt,
    LiveTransportTrace,
    build_live_metadata_execution_authorization,
    content_sha256,
    resolve_live_attempt_terminals,
    resolve_live_transport_trace,
    resolve_raw_response_body,
)

from .acquisition_executor_support import (
    _string_values,
    bytes_sha256,
)
from .acquisition_response_receipts import (
    AcquisitionSelectionError,
    R1ForensicReceipt,
    WorldBankIndicatorMetadataClassification,
    _canonical_journal_projection,
    _stable_repo_ref,
    _StrictModel,
    classify_worldbank_indicator_metadata,
)
from .catalog_candidate_admission import (
    D6RouteSelection,
)


def _require_current_journal_ref(
    ref: JournalEventRef | None,
    *,
    journal_path: Path,
) -> None:
    """Reject evidence locators that escape the journal supplied to this owner."""

    if ref is None:
        return
    if ref.journal_path != Path(journal_path).as_posix():
        raise EvidenceJournalError("journal_event_ref_unresolved", ref.event_sha256)


DEFAULT_METADATA_PROBE_OWNER = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13b_worldbank_government_balance_metadata_owner.json"
)

DEFAULT_METADATA_EXECUTION_EVIDENCE = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13b_worldbank_government_balance_metadata_evidence.json"
)

DEFAULT_D6_PRIMARY_METADATA_OWNER = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13b_worldbank_government_balance_percent_gdp_metadata_owner.json"
)

DEFAULT_D6_PRIMARY_METADATA_EVIDENCE = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13b_worldbank_government_balance_percent_gdp_metadata_evidence.json"
)


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


class D6MetadataProbeOwner(_StrictModel):
    """One zero-network owner for characterizing the selected D6 primary carrier."""

    schema_version: Literal["policyos.layer3.gy.n13b.d6_metadata_probe_owner.v1"] = (
        "policyos.layer3.gy.n13b.d6_metadata_probe_owner.v1"
    )
    route_selection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
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
            raise ValueError("D6 metadata owner projections must preserve exact scope")
        if self.owner_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("D6 metadata owner identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the timestamp-free D6 metadata owner projection."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "owner_sha256"
        }


@dataclass(frozen=True)
class _ReopenedMetadataProbe:
    """Shared journal/CAS reopening result for either metadata call owner."""

    evidence: MetadataProbeExecutionEvidence
    records: tuple[tuple[JournalEventRef, dict[str, Any], bytes], ...]
    heartbeat_elapsed: tuple[float, ...]
    raw_body: bytes | None


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


def derive_d6_metadata_probe_owner(
    *,
    selection: D6RouteSelection,
    r1_receipt: R1ForensicReceipt,
    baseline_path: Path,
    fixture_root: Path,
) -> D6MetadataProbeOwner:
    """Derive the E7/E5 owner for one D6-primary metadata characterization."""

    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    selected = D6RouteSelection.model_validate(selection.model_dump(mode="python"))
    r1 = R1ForensicReceipt.model_validate(r1_receipt.model_dump(mode="python"))
    if selected.r1_receipt_sha256 != r1.receipt_sha256:
        raise AcquisitionSelectionError("d6_metadata_r1_receipt_drift")
    if not selected.primary_requires_source_characterization:
        raise AcquisitionSelectionError("d6_metadata_characterization_not_required")
    baseline_path = Path(baseline_path)
    baseline_sha = bytes_sha256(baseline_path.read_bytes())
    if baseline_sha != selected.baseline_sha256:
        raise AcquisitionSelectionError("d6_metadata_baseline_drift")
    profile = SourceProfileRegistry.get_instance().get(selected.primary.profile_id)
    if profile is None or str(profile.connector_family) != "worldbank":
        raise AcquisitionSelectionError(
            "d6_metadata_source_profile_unresolved",
            selected.primary.profile_id,
        )
    target_slug = re.sub(r"[^a-z0-9]+", "-", selected.target_variable.casefold()).strip("-")
    basis_slug = re.sub(r"[^a-z0-9]+", "-", selected.primary.unit.casefold()).strip("-")
    attempt_id = f"gy-n13b-worldbank-wdi-{target_slug}-{basis_slug}-metadata-001"
    harness = derive_worldbank_metadata_harness_receipt(
        attempt_id=attempt_id,
        indicator_id=selected.primary.request_dataset_id,
        profile_id=selected.primary.profile_id,
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
        "connector_id": selected.primary.connector_id,
        "profile_id": selected.primary.profile_id,
        "variable_id": selected.primary.request_dataset_id,
        "request_variables": [selected.primary.request_dataset_id],
        "endpoint_url": harness.endpoint_url,
        "params": harness.params,
        "schema_contract": schema_contract,
        "source_lane": "shadow_characterization",
        "response_admitted": False,
        "route_selection_sha256": selected.selection_sha256,
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
        "schema_version": "policyos.layer3.gy.n13b.d6_metadata_probe_owner.v1",
        "route_selection_sha256": selected.selection_sha256,
        "r1_receipt_sha256": r1.receipt_sha256,
        "baseline_ref": _stable_repo_ref(baseline_path),
        "baseline_sha256": baseline_sha,
        "request": request,
        "harness": harness,
        "authorization": authorization,
    }
    return D6MetadataProbeOwner(
        **values,
        owner_sha256=content_sha256(values),
    )


def _reopen_metadata_probe_execution_evidence(
    *,
    owner: MetadataProbeOwner | D6MetadataProbeOwner,
    indicator_id: str,
    journal_path: Path,
    cas_root: Path,
    baseline_path: Path,
) -> _ReopenedMetadataProbe:
    """Reopen one metadata attempt through the shared journal/CAS evidence owner."""

    baseline_path = Path(baseline_path)
    baseline_sha = bytes_sha256(baseline_path.read_bytes())
    if baseline_sha != owner.baseline_sha256:
        raise AcquisitionSelectionError("metadata_baseline_mutation", baseline_path.as_posix())
    if owner.baseline_ref != _stable_repo_ref(baseline_path):
        raise AcquisitionSelectionError("metadata_baseline_ref_drift", owner.baseline_ref)
    records = _canonical_journal_projection(Path(journal_path))
    attempt_id = owner.authorization.attempt_id
    terminals = {
        terminal.attempt_id: terminal
        for terminal in resolve_live_attempt_terminals(Path(journal_path))
    }
    terminal = terminals.get(attempt_id)
    if terminal is None:
        raise AcquisitionSelectionError("metadata_attempt_terminal_unresolved", attempt_id)
    _require_current_journal_ref(terminal.request_ref, journal_path=journal_path)
    _require_current_journal_ref(terminal.raw_evidence_ref, journal_path=journal_path)
    request_events = tuple(
        (ref, event)
        for ref, event, _payload in records
        if event.get("event_kind") == "request" and event.get("attempt_id") == attempt_id
    )
    if len(request_events) != 1:
        raise AcquisitionSelectionError("metadata_request_unresolved", attempt_id)
    request_ref, request_event = request_events[0]
    _require_current_journal_ref(request_ref, journal_path=journal_path)
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
            indicator_id=indicator_id,
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
        for transport_ref in (
            transport_trace.request_ref,
            transport_trace.transport_attempt_ref,
            *transport_trace.heartbeat_refs,
            transport_trace.raw_evidence_ref,
        ):
            _require_current_journal_ref(transport_ref, journal_path=journal_path)
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
    return _ReopenedMetadataProbe(
        evidence=MetadataProbeExecutionEvidence(
            **values,
            evidence_sha256=content_sha256(values),
        ),
        records=records,
        heartbeat_elapsed=heartbeat_elapsed,
        raw_body=raw_body,
    )


def derive_d6_metadata_probe_execution_evidence(
    *,
    owner: D6MetadataProbeOwner,
    selection: D6RouteSelection,
    journal_path: Path,
    cas_root: Path,
    baseline_path: Path,
) -> MetadataProbeExecutionEvidence:
    """Reopen the D6 primary metadata call without admitting its response."""

    resolved_owner = D6MetadataProbeOwner.model_validate(owner.model_dump(mode="python"))
    selected = D6RouteSelection.model_validate(selection.model_dump(mode="python"))
    if resolved_owner.route_selection_sha256 != selected.selection_sha256:
        raise AcquisitionSelectionError("d6_metadata_route_selection_drift")
    reopened = _reopen_metadata_probe_execution_evidence(
        owner=resolved_owner,
        indicator_id=selected.primary.request_dataset_id,
        journal_path=journal_path,
        cas_root=cas_root,
        baseline_path=baseline_path,
    )
    return reopened.evidence


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
    reopened = _reopen_metadata_probe_execution_evidence(
        owner=owner,
        indicator_id=r1.request_dataset_id,
        journal_path=journal_path,
        cas_root=cas_root,
        baseline_path=baseline_path,
    )
    execution_evidence = reopened.evidence
    attempt_id = execution_evidence.attempt_id
    request_ref = execution_evidence.request_ref
    raw_ref = execution_evidence.raw_evidence_ref
    terminal = execution_evidence.terminal
    raw_body_sha = execution_evidence.raw_body_sha256
    raw_body = reopened.raw_body
    heartbeat_elapsed = reopened.heartbeat_elapsed
    store = FileSystemCAS(Path(cas_root), ownership_enforced=False)
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
