"""Owner-validated projection service for reviewer confidence risk-spend packets."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from fractions import Fraction
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from polisyos.runtime.http.services.confidence_ledger_risk_spend_contracts import (
    PROJECTION_RULE_VERSION,
    STABLE_ADDRESS,
    ArtifactMissingConfidenceLedgerRiskSpendPacket,
    AvailableConfidenceLedgerRiskSpendPacket,
    ConfidenceLedgerRiskSpendAvailability,
    ConfidenceLedgerRiskSpendPacket,
    ConfidenceLedgerRiskSpendReplayPins,
    InvalidConfidenceLedgerRiskSpendPacket,
    SourceBlockedConfidenceLedgerRiskSpendPacket,
    SourceBlockedReason,
)
from polisyos.runtime.http.services.export_replay import (
    build_export_replay_address,
    hash_export_projection,
)
from polisyos.runtime.http.services.governed_projections import (
    CONFIDENCE_LEDGER_GUARDED_SCHEMA_VERSION,
    CONFIDENCE_LEDGER_GUARDED_SOURCE_PATH,
    CONFIDENCE_LEDGER_GUARDED_VALIDATOR_ID,
    CONFIDENCE_LEDGER_GUARDED_VALIDATOR_VERSION,
    GovernedProjectionService,
    GuardedProjectionId,
    GuardedProjectionSourceResolution,
    ProjectionAvailability,
    ProjectionSourceValidation,
    ReplayPinMismatchError,
)
from polisyos.runtime.quality.confidence_ledger import (
    ConfidenceLedgerRegistry,
    ConfidenceLedgerSemanticReceiptProjection,
    load_confidence_ledger_registry,
)
from polisyos.runtime.quality.confidence_ledger_surface import (
    ConfidenceLedgerRiskSpendProjection,
    admit_confidence_ledger_risk_spend_projection,
    project_confidence_ledger_risk_spend,
)
from polisyos.runtime.quality.obligation_coverage import (
    CoverageDerivationContext,
    build_coverage_envelope,
)

OVER_SPEND_OWNER_DIAGNOSTIC_CODES = (
    "semantic_forged_spend_row",
    "semantic_total_spend_drift",
    "semantic_budget_status_drift",
    "semantic_deterministic_spend_nonzero",
    "deterministic_real_run_spend_nonzero",
)
_OVER_SPEND_OWNER_DIAGNOSTIC_SET = frozenset(OVER_SPEND_OWNER_DIAGNOSTIC_CODES)
_PROTECTED_ACTION_ID = "protected-action://ds17/review-risk-spend"
_SEMANTIC_SOURCE_REF = CONFIDENCE_LEDGER_GUARDED_SOURCE_PATH + "#real_ledger_projection"


def derive_over_spend_allowset() -> tuple[str, ...]:
    """Return the complete N11 spend/determinism diagnostic denominator."""

    return OVER_SPEND_OWNER_DIAGNOSTIC_CODES


def validate_over_spend_allowset(*, derived_codes: tuple[str, ...]) -> None:
    """Fail if a caller narrows, widens, or duplicates the owner denominator."""

    if (
        len(derived_codes) != len(_OVER_SPEND_OWNER_DIAGNOSTIC_SET)
        or frozenset(derived_codes) != _OVER_SPEND_OWNER_DIAGNOSTIC_SET
    ):
        raise ValueError("DS17 over-spend owner diagnostic allowset mismatch")


def _classify_over_spend_owner_failure(
    *,
    issue_codes: tuple[str, ...],
    source_payload_equal: bool,
    recomputed_total_spend: Fraction,
    registry_delta: Fraction,
) -> SourceBlockedReason | None:
    """Select the sole safe source blocker from worker-recomputed predicates."""

    normalized = frozenset(code for code in issue_codes if code)
    if (
        normalized
        and normalized.issubset(_OVER_SPEND_OWNER_DIAGNOSTIC_SET)
        and len(normalized) == len(issue_codes)
        and source_payload_equal is True
        and Fraction(recomputed_total_spend) > Fraction(registry_delta)
    ):
        return SourceBlockedReason.OVER_SPEND
    return None


class ConfidenceLedgerRiskSpendProjectionService:
    """Execute guarded owner validation and compose one HTTP packet per request."""

    def __init__(
        self,
        repository_root: Path,
    ) -> None:
        self._repository_root = repository_root

    def get(
        self,
        *,
        artifact_content_hash: str | None = None,
        projection_hash: str | None = None,
        source_dependency_hash: str | None = None,
        source_as_of: datetime | None = None,
        projection_rule_version: str | None = None,
    ) -> ConfidenceLedgerRiskSpendPacket:
        """Execute the guarded owner worker and enforce every replay pin exactly."""

        resolution = GovernedProjectionService(self._repository_root).resolve_guarded_source(
            GuardedProjectionId.CONFIDENCE_LEDGER_RISK_SPEND
        )
        packet = self._project_resolution(resolution)
        _enforce_replay_pins(
            packet,
            artifact_content_hash=artifact_content_hash,
            projection_hash=projection_hash,
            source_dependency_hash=source_dependency_hash,
            source_as_of=source_as_of,
            projection_rule_version=projection_rule_version,
        )
        return packet

    def _project_resolution(
        self,
        resolution: GuardedProjectionSourceResolution,
    ) -> ConfidenceLedgerRiskSpendPacket:
        if resolution.availability is ProjectionAvailability.ARTIFACT_MISSING:
            return ArtifactMissingConfidenceLedgerRiskSpendPacket(
                availability=ConfidenceLedgerRiskSpendAvailability.ARTIFACT_MISSING,
                source_schema_version=None,
                source_rule_version=None,
                as_of=resolution.as_of,
                freshness=resolution.freshness,
                absence_reason="governed confidence-ledger source is absent",
            )
        if (
            resolution.source is None
            or resolution.validation is None
            or resolution.projection_payload is None
            or resolution.source_document is None
        ):
            return _invalid_packet(resolution)

        try:
            registry, registry_projection_hash = _admit_owner_resolution(
                resolution,
                repository_root=self._repository_root,
            )
        except (KeyError, OSError, TypeError, ValueError):
            return _invalid_packet(resolution)
        validation = resolution.validation
        source_blocker = _source_blocker(validation)
        if source_blocker is not None:
            return _source_blocked_packet(resolution, source_blocker)
        if resolution.availability is not ProjectionAvailability.AVAILABLE:
            return _invalid_packet(resolution)

        try:
            semantic = resolution.projection_payload
            derivation_context = CoverageDerivationContext(
                protected_action_id=_PROTECTED_ACTION_ID,
                semantic_source_ref=_SEMANTIC_SOURCE_REF,
                semantic_source_verifier_ref=(CONFIDENCE_LEDGER_GUARDED_VALIDATOR_ID),
            )
            envelope = build_coverage_envelope(
                registry=registry,
                semantic_ledger=semantic,
                derivation_context=derivation_context,
            )
            candidate = project_confidence_ledger_risk_spend(
                registry=registry,
                semantic_ledger=semantic,
                derivation_context=derivation_context,
                coverage_envelope=envelope,
            )
            admitted = admit_confidence_ledger_risk_spend_projection(
                candidate,
                registry=registry,
                semantic_ledger=semantic,
                derivation_context=derivation_context,
            )
            if admitted.status != "exact":
                raise ValueError("confidence_domain_projection_not_exact")
        except (KeyError, TypeError, ValueError):
            return _invalid_packet(resolution)
        return _available_packet(
            resolution,
            registry=registry,
            registry_projection_hash=registry_projection_hash,
            payload=admitted.projection,
        )


def _admit_owner_resolution(
    resolution: GuardedProjectionSourceResolution,
    *,
    repository_root: Path,
) -> tuple[ConfidenceLedgerRegistry, str]:
    """Reconcile every owner fact before any transport or C01 derivation."""

    source = resolution.source
    validation = resolution.validation
    source_document = resolution.source_document
    semantic = resolution.projection_payload
    if (
        resolution.projection_id is not GuardedProjectionId.CONFIDENCE_LEDGER_RISK_SPEND
        or source is None
        or validation is None
        or source_document is None
        or semantic is None
        or source.relative_path != CONFIDENCE_LEDGER_GUARDED_SOURCE_PATH
        or source.validation != validation
        or validation.validator_id != CONFIDENCE_LEDGER_GUARDED_VALIDATOR_ID
        or validation.validator_version != CONFIDENCE_LEDGER_GUARDED_VALIDATOR_VERSION
        or resolution.source_schema_version != CONFIDENCE_LEDGER_GUARDED_SCHEMA_VERSION
        or resolution.source_rule_version is not None
        or validation.worker_validation_receipt_hash is None
        or validation.source_payload_equal is not True
        or validation.bound_artifact_content_hash != source.artifact_content_hash
        or validation.bound_dependency_aggregate_identity != resolution.source_dependency_hash
    ):
        raise ValueError("confidence_owner_intake_identity_mismatch")

    source_path = repository_root / CONFIDENCE_LEDGER_GUARDED_SOURCE_PATH
    raw_source = source_path.read_bytes()
    actual_artifact_hash = f"sha256:{hashlib.sha256(raw_source).hexdigest()}"
    parsed_source = json.loads(raw_source)
    if (
        actual_artifact_hash != source.artifact_content_hash
        or not isinstance(parsed_source, Mapping)
        or parsed_source != source_document
    ):
        raise ValueError("confidence_owner_intake_source_mismatch")

    raw_semantic = source_document.get("real_ledger_projection")
    admitted_semantic = ConfidenceLedgerSemanticReceiptProjection.model_validate_json(
        json.dumps(raw_semantic, separators=(",", ":"), sort_keys=True),
        strict=True,
    )
    if admitted_semantic.model_dump(mode="json") != semantic.model_dump(mode="json"):
        raise ValueError("confidence_owner_intake_semantic_mismatch")

    registry, registry_projection_hash = _load_registry_projection(source_document)
    if (
        validation.registry_content_hash != registry.content_hash
        or validation.registry_projection_hash != registry_projection_hash
        or validation.frozen_semantic_projection_hash != admitted_semantic.projection_hash
    ):
        raise ValueError("confidence_owner_intake_registry_mismatch")

    if resolution.availability is ProjectionAvailability.AVAILABLE:
        if (
            validation.status != "passed"
            or validation.issue_codes != ()
            or validation.semantic_projection_hash != admitted_semantic.projection_hash
        ):
            raise ValueError("confidence_owner_intake_available_mismatch")
    elif validation.status != "failed" or not validation.issue_codes:
        raise ValueError("confidence_owner_intake_failed_mismatch")
    return registry, registry_projection_hash


def _load_registry_projection(
    source_document: Mapping[str, Any],
) -> tuple[ConfidenceLedgerRegistry, str]:
    raw_projection = source_document.get("registry_projection")
    if not isinstance(raw_projection, Mapping):
        raise ValueError("confidence_registry_projection_missing")
    fields = (
        "policy",
        "obligation_pools",
        "proof_profiles",
        "schedule_profiles",
        "instruments",
        "certificate_class_routes",
    )
    registry_payload = {field: raw_projection[field] for field in fields}
    registry_payload["schema_version"] = raw_projection["registry_schema_version"]
    registry = load_confidence_ledger_registry(registry_payload)
    if registry.content_hash != raw_projection.get("registry_content_hash"):
        raise ValueError("confidence_registry_content_hash_mismatch")
    registry_projection_hash = raw_projection.get("projection_hash")
    if not isinstance(registry_projection_hash, str):
        raise ValueError("confidence_registry_projection_hash_missing")
    return registry, registry_projection_hash


def _source_blocker(
    validation: ProjectionSourceValidation,
) -> SourceBlockedReason | None:
    if validation.status != "failed" or validation.worker_validation_receipt_hash is None:
        return None
    required = (
        validation.recomputed_total_spend_numerator,
        validation.recomputed_total_spend_denominator,
        validation.registry_delta_numerator,
        validation.registry_delta_denominator,
    )
    if any(value is None for value in required):
        return None
    try:
        recomputed_total = Fraction(required[0], required[1])
        registry_delta = Fraction(required[2], required[3])
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return _classify_over_spend_owner_failure(
        issue_codes=validation.issue_codes,
        source_payload_equal=validation.source_payload_equal is True,
        recomputed_total_spend=recomputed_total,
        registry_delta=registry_delta,
    )


def _available_packet(
    resolution: GuardedProjectionSourceResolution,
    *,
    registry: ConfidenceLedgerRegistry,
    registry_projection_hash: str,
    payload: ConfidenceLedgerRiskSpendProjection,
) -> AvailableConfidenceLedgerRiskSpendPacket:
    source = resolution.source
    validation = resolution.validation
    source_dependency_hash = resolution.source_dependency_hash
    if (
        source is None
        or validation is None
        or source_dependency_hash is None
        or validation.worker_validation_receipt_hash is None
        or validation.frozen_semantic_projection_hash is None
    ):
        raise ValueError("confidence_available_source_identity_incomplete")
    receipt_hash = validation.worker_validation_receipt_hash
    body: dict[str, object] = {
        **_common_body(resolution),
        "availability": ConfidenceLedgerRiskSpendAvailability.AVAILABLE,
        "source": source,
        "source_dependency_hash": source_dependency_hash,
        "registry_content_hash": registry.content_hash,
        "registry_projection_hash": registry_projection_hash,
        "frozen_semantic_projection_hash": validation.frozen_semantic_projection_hash,
        "worker_validation_receipt_ref": f"owner-validation:{receipt_hash}",
        "worker_validation_receipt_hash": receipt_hash,
        "payload": payload,
        "source_blocked_reason": None,
        "absence_reason": None,
    }
    projection_hash = hash_export_projection(_packet_identity_body(body, resolution))
    replay_pins = ConfidenceLedgerRiskSpendReplayPins(
        artifact_content_hash=source.artifact_content_hash,
        source_dependency_hash=source_dependency_hash,
        projection_hash=projection_hash,
        source_as_of=resolution.as_of,
    )
    return AvailableConfidenceLedgerRiskSpendPacket(
        **body,
        replay_pins=replay_pins,
        projection_hash=projection_hash,
        replay_address=build_export_replay_address(
            STABLE_ADDRESS,
            replay_pins.model_dump(mode="json"),
        ),
    )


def _source_blocked_packet(
    resolution: GuardedProjectionSourceResolution,
    reason: SourceBlockedReason,
) -> SourceBlockedConfidenceLedgerRiskSpendPacket | InvalidConfidenceLedgerRiskSpendPacket:
    source = resolution.source
    validation = resolution.validation
    source_dependency_hash = resolution.source_dependency_hash
    if (
        source is None
        or validation is None
        or validation.worker_validation_receipt_hash is None
        or source_dependency_hash is None
    ):
        return _invalid_packet(resolution)
    receipt_hash = validation.worker_validation_receipt_hash
    body: dict[str, object] = {
        **_common_body(resolution),
        "availability": ConfidenceLedgerRiskSpendAvailability.SOURCE_BLOCKED,
        "source_blocked_reason": reason,
        "source_artifact_content_hash": source.artifact_content_hash,
        "source_dependency_hash": source_dependency_hash,
        "worker_validation_receipt_ref": f"owner-validation:{receipt_hash}",
        "worker_validation_receipt_hash": receipt_hash,
        "absence_reason": None,
    }
    projection_hash = hash_export_projection(_packet_identity_body(body, resolution))
    replay_pins = ConfidenceLedgerRiskSpendReplayPins(
        artifact_content_hash=source.artifact_content_hash,
        source_dependency_hash=source_dependency_hash,
        projection_hash=projection_hash,
        source_as_of=resolution.as_of,
    )
    return SourceBlockedConfidenceLedgerRiskSpendPacket(
        **body,
        replay_pins=replay_pins,
        projection_hash=projection_hash,
        replay_address=build_export_replay_address(
            STABLE_ADDRESS,
            replay_pins.model_dump(mode="json"),
        ),
    )


def _invalid_packet(
    resolution: GuardedProjectionSourceResolution,
) -> InvalidConfidenceLedgerRiskSpendPacket:
    source_hash = resolution.source.artifact_content_hash if resolution.source is not None else None
    receipt_hash = (
        resolution.validation.worker_validation_receipt_hash
        if resolution.validation is not None
        else None
    )
    return InvalidConfidenceLedgerRiskSpendPacket(
        availability=ConfidenceLedgerRiskSpendAvailability.INVALID_SOURCE,
        source_schema_version=resolution.source_schema_version,
        source_rule_version=resolution.source_rule_version,
        as_of=resolution.as_of,
        freshness=resolution.freshness,
        source_artifact_content_hash=source_hash,
        worker_validation_receipt_ref=(
            f"owner-validation:{receipt_hash}" if receipt_hash is not None else None
        ),
        worker_validation_receipt_hash=receipt_hash,
        absence_reason="confidence-ledger source failed owner admission",
    )


def _common_body(resolution: GuardedProjectionSourceResolution) -> dict[str, object]:
    return {
        "packet_schema_version": ("policyos.runtime.confidence_ledger_risk_spend_packet.v1"),
        "export_replay_contract": "policyos.runtime.export_replay_binding.v1",
        "projection_id": GuardedProjectionId.CONFIDENCE_LEDGER_RISK_SPEND.value,
        "projection_rule_version": PROJECTION_RULE_VERSION,
        "intended_audience": "REVIEWER",
        "intended_audiences": ("REVIEWER", "EXPERT", "MACHINE"),
        "authoritative_for": (
            "conditionality_disclosure",
            "declared_set_accounting",
            "source_validation_posture",
        ),
        "may_not_use_for": (
            "promotion_authority",
            "publication_authority",
            "public_audience",
            "bounded_completeness",
        ),
        "source_schema_version": resolution.source_schema_version,
        "source_rule_version": resolution.source_rule_version,
        "as_of": resolution.as_of,
        "freshness": resolution.freshness,
        "stable_address": STABLE_ADDRESS,
    }


def _packet_identity_body(
    body: Mapping[str, object],
    resolution: GuardedProjectionSourceResolution,
) -> dict[str, object]:
    """Exclude request-observation time from stable packet identity."""

    freshness = resolution.freshness.model_dump(
        mode="json",
        exclude={"observed_at"},
    )
    return {
        **body,
        "as_of": _replay_datetime(resolution.as_of),
        "freshness": freshness,
    }


def _enforce_replay_pins(
    packet: ConfidenceLedgerRiskSpendPacket,
    *,
    artifact_content_hash: str | None,
    projection_hash: str | None,
    source_dependency_hash: str | None,
    source_as_of: datetime | None,
    projection_rule_version: str | None,
) -> None:
    actual_artifact_hash = getattr(packet, "source_artifact_content_hash", None)
    if isinstance(packet, AvailableConfidenceLedgerRiskSpendPacket):
        actual_artifact_hash = packet.source.artifact_content_hash
    values = (
        ("artifact_content_hash", artifact_content_hash, actual_artifact_hash),
        ("projection_hash", projection_hash, getattr(packet, "projection_hash", None)),
        (
            "source_dependency_hash",
            source_dependency_hash,
            getattr(packet, "source_dependency_hash", None),
        ),
        (
            "projection_rule_version",
            projection_rule_version,
            packet.projection_rule_version,
        ),
    )
    for field, expected, actual in values:
        if expected is not None and expected != actual:
            raise ReplayPinMismatchError(field, expected=expected, actual=actual)
    if source_as_of is not None:
        expected_time = _normalize_datetime(source_as_of)
        actual_time = _normalize_datetime(packet.as_of)
        if expected_time != actual_time:
            raise ReplayPinMismatchError(
                "source_as_of",
                expected=_replay_datetime(expected_time),
                actual=_replay_datetime(actual_time),
            )


def _normalize_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _replay_datetime(value: datetime) -> str:
    return _normalize_datetime(value).isoformat().replace("+00:00", "Z")


__all__ = [
    "OVER_SPEND_OWNER_DIAGNOSTIC_CODES",
    "ConfidenceLedgerRiskSpendProjectionService",
    "derive_over_spend_allowset",
    "validate_over_spend_allowset",
]
