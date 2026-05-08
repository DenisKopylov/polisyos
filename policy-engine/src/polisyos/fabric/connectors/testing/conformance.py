"""Connector conformance harness v2 for SourceContract-backed sources."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from polisyos.fabric.connectors.base import SourceConnector
from polisyos.fabric.connectors.capabilities import validate_protocol_compliance
from polisyos.fabric.connectors.contracts import ConnectorSchemaContract, SourceContract
from polisyos.fabric.connectors.governance_metadata import (
    validate_connector_governance_metadata,
)
from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.connectors.profiles.resolver import resolve_execution_policy
from polisyos.fabric.connectors.testing.harness import ConnectorTestHarness
from polisyos.fabric.quality.processing_guarantees import ProcessingGuarantee


@dataclass(frozen=True, slots=True)
class ConformanceIssue:
    """One SourceContract v2 conformance issue."""

    check_id: str
    message: str
    severity: str = "error"
    evidence: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ConformanceReport:
    """Conformance result for one connector/source contract pair."""

    connector_id: str
    source_contract_id: str
    issues: tuple[ConformanceIssue, ...]

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def issues_by_check(self) -> dict[str, list[ConformanceIssue]]:
        grouped: dict[str, list[ConformanceIssue]] = {}
        for issue in self.issues:
            grouped.setdefault(issue.check_id, []).append(issue)
        return grouped


def validate_source_conformance_v2(
    *,
    connector_class: type[SourceConnector],
    source_contract: SourceContract,
    profiles: Iterable[SourceProfile] = (),
    schema_contracts: Iterable[ConnectorSchemaContract] = (),
    replay_fixture_exists: bool | None = None,
) -> ConformanceReport:
    """Validate connector/source evidence before production visibility."""

    issues: list[ConformanceIssue] = []
    connector_id = str(getattr(connector_class, "connector_id", ""))
    metadata = connector_class.metadata

    for violation in validate_protocol_compliance(connector_class):
        issues.append(ConformanceIssue("protocol_compliance", violation))

    governance = validate_connector_governance_metadata(metadata)
    for issue in governance.issues:
        issues.append(
            ConformanceIssue(
                "governance_metadata",
                f"{issue.field}: {issue.message}",
                evidence={"connector_id": issue.connector_id},
            )
        )

    expected_id = f"{metadata.namespace}.{metadata.connector_id}"
    if source_contract.source.connector_id != expected_id:
        issues.append(
            ConformanceIssue(
                "source_identity",
                (
                    "SourceContract connector_id does not match connector metadata "
                    f"({source_contract.source.connector_id!r} != {expected_id!r})"
                ),
            )
        )
    if connector_id and connector_id not in {
        source_contract.source.connector_id,
        metadata.connector_id,
        expected_id,
    }:
        issues.append(
            ConformanceIssue(
                "source_identity",
                f"Connector class id {connector_id!r} is not represented in SourceContract",
            )
        )

    profiles_by_id = {profile.profile_id: profile for profile in profiles}
    source_profile = profiles_by_id.get(source_contract.source.profile_id)
    if source_profile is None:
        issues.append(
            ConformanceIssue(
                "profile_resolution",
                f"profile_id {source_contract.source.profile_id!r} is not registered",
            )
        )

    schema_contract_ids = {contract.contract_id for contract in schema_contracts}
    schema_ref = source_contract.schema.schema_contract_ref or ""
    if source_contract.schema.fields or any(contract_id in schema_ref for contract_id in schema_contract_ids):
        pass
    elif not source_contract.schema.has_schema_evidence:
        issues.append(ConformanceIssue("schema_contract", "schema evidence is missing"))

    if not source_contract.quality.contract_ref:
        issues.append(ConformanceIssue("quality_contract", "quality contract ref is missing"))
    if not source_contract.quality.required_checks:
        issues.append(ConformanceIssue("quality_contract", "required quality checks are empty"))

    if source_contract.status == "active" and not source_contract.replay.fixture_ref:
        issues.append(
            ConformanceIssue(
                "replay_fixture",
                "production-visible active sources require a replay fixture",
            )
        )
    elif source_contract.replay.fixture_ref:
        if replay_fixture_exists is False:
            issues.append(
                ConformanceIssue(
                    "replay_fixture",
                    f"replay fixture not found: {source_contract.replay.fixture_ref}",
                )
            )
    elif not source_contract.replay.non_replayable_reason:
        issues.append(
            ConformanceIssue(
                "replay_fixture",
                "source must carry replay fixture or explicit non-replayable reason",
            )
        )

    if not source_contract.lineage.seed_node_kind:
        issues.append(ConformanceIssue("lineage_seed", "lineage seed_node_kind is missing"))

    if source_contract.security.safe_filters_required and not _has_safe_filter_evidence(
        source_contract
    ):
        issues.append(
            ConformanceIssue(
                "safe_filters",
                "safe filter evidence must be declared in required_checks or security contract",
                severity="warning",
            )
        )

    _validate_bounded_read_evidence(
        connector_class=connector_class,
        source_profile=source_profile,
        source_contract=source_contract,
        issues=issues,
    )

    if source_contract.security.classification not in {
        "public",
        "internal",
        "confidential",
        "regulated_pii",
        "sensitive_policy_legal_signal",
    }:
        issues.append(ConformanceIssue("access_classification", "invalid classification"))
    _validate_field_access_policies(source_contract, issues)
    if source_contract.retention.artifact_retention_days < source_contract.retention.min_retention_days:
        issues.append(ConformanceIssue("retention", "artifact retention is shorter than minimum"))

    _validate_slo_metadata(source_contract, issues)
    _validate_processing_guarantee(source_contract, issues)

    return ConformanceReport(
        connector_id=expected_id,
        source_contract_id=source_contract.id,
        issues=tuple(issues),
    )


def _has_safe_filter_evidence(contract: SourceContract) -> bool:
    checks = {check.casefold() for check in contract.quality.required_checks}
    return "safe_filters" in checks or "safe_filter_validation" in checks


def _validate_field_access_policies(
    source_contract: SourceContract,
    issues: list[ConformanceIssue],
) -> None:
    policies = tuple(source_contract.security.field_policies)
    if not policies:
        issues.append(
            ConformanceIssue(
                "access_classification",
                "field access policies are required for production-visible sources",
            )
        )
        return
    policy_ids = {policy.field_id for policy in policies}
    field_ids = {field.stable_id for field in source_contract.schema.fields}
    if field_ids and "*" not in policy_ids:
        missing = sorted(field_ids - policy_ids)
        if missing:
            issues.append(
                ConformanceIssue(
                    "access_classification",
                    "field access policies missing schema field coverage",
                    evidence={"missing_field_ids": tuple(missing[:16])},
                )
            )
    if not field_ids and "*" not in policy_ids:
        issues.append(
            ConformanceIssue(
                "access_classification",
                "template sources require wildcard field access policy",
            )
        )
    for policy in policies:
        if (
            policy.classification != "public"
            or policy.pii_tier != "none"
            or policy.tenant_scope != "shared_public"
            or policy.redaction != "none"
        ) and not policy.policy_ref:
            issues.append(
                ConformanceIssue(
                    "access_classification",
                    f"field policy {policy.field_id!r} requires policy_ref",
                )
            )


def _has_bounded_read_check(contract: SourceContract) -> bool:
    checks = {check.casefold() for check in contract.quality.required_checks}
    return "bounded_reads" in checks or "bounded_response" in checks


def _validate_bounded_read_evidence(
    *,
    connector_class: type[SourceConnector],
    source_profile: SourceProfile | None,
    source_contract: SourceContract,
    issues: list[ConformanceIssue],
) -> None:
    """Require explicit bounded-read evidence in contract, profile, or runtime."""

    has_contract_check = _has_bounded_read_check(source_contract)
    runtime_profile = getattr(connector_class, "resilience_profile", None)
    runtime_limits = {
        "max_response_bytes": getattr(runtime_profile, "max_response_bytes", None),
        "max_json_bytes": getattr(runtime_profile, "max_json_bytes", None),
        "max_decompressed_bytes": getattr(
            runtime_profile, "max_decompressed_bytes", None
        ),
        "max_rows": getattr(runtime_profile, "max_rows", None),
    }
    profile_limits: dict[str, int | float | str | None] = {}
    if source_profile is not None:
        policy = resolve_execution_policy(source_profile)
        profile_limits = {
            "timeout_seconds": source_profile.timeout_seconds,
            "max_concurrency": policy.max_concurrency,
            "requests_per_hour": policy.requests_per_hour,
            "rate_limit_rps": source_profile.rate_limit_rps,
            "core_group_limit": policy.core_group_limit,
            "backfill_group_limit": policy.backfill_group_limit,
            "max_sync_cells": policy.max_sync_cells,
            "max_async_cells": policy.max_async_cells,
            "bulk_format": policy.bulk_format,
        }

    has_profile_bound = any(
        value not in {None, "", 0}
        for key, value in profile_limits.items()
        if key != "timeout_seconds"
    )
    has_runtime_bound = any(value is not None and value > 0 for value in runtime_limits.values())
    has_timeout_bound = (
        source_profile is not None and int(source_profile.timeout_seconds or 0) > 0
    )

    if not has_contract_check:
        issues.append(
            ConformanceIssue(
                "bounded_reads",
                "SourceContract quality.required_checks must include bounded_reads",
                evidence={
                    "required_checks": tuple(source_contract.quality.required_checks),
                },
            )
        )
    if not has_timeout_bound:
        issues.append(
            ConformanceIssue(
                "bounded_reads",
                "source profile must declare a positive timeout_seconds value",
                evidence={"profile_id": source_contract.source.profile_id},
            )
        )
    if not (has_profile_bound or has_runtime_bound):
        issues.append(
            ConformanceIssue(
                "bounded_reads",
                "source profile or connector runtime must declare finite read limits",
                evidence={
                    "profile_limits": profile_limits,
                    "runtime_limits": runtime_limits,
                },
            )
        )


def _validate_slo_metadata(contract: SourceContract, issues: list[ConformanceIssue]) -> None:
    if not 0.0 <= contract.sla.availability_target <= 1.0:
        issues.append(ConformanceIssue("slo_metadata", "availability target is invalid"))
    if contract.sla.freshness_slo_seconds < 0:
        issues.append(ConformanceIssue("slo_metadata", "freshness SLO is negative"))
    if contract.sla.p95_latency_ms < 0:
        issues.append(ConformanceIssue("slo_metadata", "p95 latency is negative"))
    if not 0.0 <= contract.sla.replay_success_target <= 1.0:
        issues.append(ConformanceIssue("slo_metadata", "replay success target is invalid"))


def _validate_processing_guarantee(
    contract: SourceContract,
    issues: list[ConformanceIssue],
) -> None:
    processing = contract.processing
    guarantee = ProcessingGuarantee(processing.guarantee)
    if guarantee == ProcessingGuarantee.EXACTLY_ONCE_NARROW:
        if processing.atomicity_proof is None or not processing.atomicity_proof.complete:
            issues.append(
                ConformanceIssue(
                    "processing_guarantee",
                    "exactly_once_narrow requires atomic input/state/output proof",
                )
            )
    if guarantee in {
        ProcessingGuarantee.AT_LEAST_ONCE_WITH_DEDUPE,
        ProcessingGuarantee.EFFECTIVELY_ONCE,
    } and (not processing.idempotency.enabled or not processing.idempotency.key_fields):
        issues.append(
            ConformanceIssue(
                "idempotency_dedupe",
                "dedupe-capable guarantees require visible dedupe key policy",
            )
        )
    if processing.idempotency.dedupe_window_seconds <= 0:
        issues.append(
            ConformanceIssue(
                "idempotency_dedupe",
                "dedupe window must be visible and positive",
            )
        )
    if processing.idempotency.replay_retention_days < contract.retention.min_retention_days:
        issues.append(
            ConformanceIssue(
                "replay_retention",
                "processing replay retention must cover minimum source retention",
            )
        )


class ConnectorConformanceHarnessV2(ConnectorTestHarness):
    """Pytest harness extension that reuses ConnectorTestHarness v1 pillars."""

    source_contract: ClassVar[SourceContract]
    source_profiles: ClassVar[tuple[SourceProfile, ...]] = ()
    schema_contracts: ClassVar[tuple[ConnectorSchemaContract, ...]] = ()
    replay_fixture_exists: ClassVar[bool | None] = None

    def test_source_contract_v2_conformance(self) -> None:
        """Validate SourceContract v2 evidence alongside protocol harness tests."""

        report = validate_source_conformance_v2(
            connector_class=self.connector_class,
            source_contract=self.source_contract,
            profiles=self.source_profiles,
            schema_contracts=self.schema_contracts,
            replay_fixture_exists=self.replay_fixture_exists,
        )
        assert report.passed, [
            f"{issue.check_id}: {issue.message}" for issue in report.issues
        ]


__all__ = [
    "ConformanceIssue",
    "ConformanceReport",
    "ConnectorConformanceHarnessV2",
    "validate_source_conformance_v2",
]
