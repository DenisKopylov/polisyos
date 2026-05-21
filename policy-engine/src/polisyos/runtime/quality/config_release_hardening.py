"""Policy Design Case config/release/deployment/migration hardening records."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

CONFIG_RELEASE_HARDENING_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.config_release_deployment_migration_hardening.v1"
)
CONFIG_RELEASE_HARDENING_CONTRACT_ID = (
    "policy_design_case.config_release_deployment_migration_hardening.v1"
)
CONFIG_RELEASE_HARDENING_RECORD_FAMILY = "publication_trust_and_external_governance.v1"
CONFIG_RELEASE_HARDENING_PDD_IDS = (
    "PDD-072",
    "PDD-075",
    "PDD-076",
    "PDD-079",
    "PDD-080",
    "PDD-081",
    "PDD-082",
)
REQUIRED_DEPLOYMENT_SERVICES = frozenset(
    {
        "authz_opa",
        "state_store",
        "generated_clients",
        "resource_quotas",
        "release_gates",
    }
)
REQUIRED_GENERATED_SURFACES = frozenset(
    {
        "openapi",
        "generated_client",
        "dashboard_validator",
        "cli",
        "docs",
        "release_snapshot",
    }
)
_PASS_STATUSES = frozenset({"pass", "passed", "match", "matched", "ok", "clean"})
_ACTIVE_BLOCKER_STATUSES = frozenset(
    {"active", "blocked", "blocking", "fail", "failed", "open", "stale", "unresolved"}
)
_SHA_REF_RE = re.compile(r"^(?:sha256:|cas://sha256/)[0-9a-f]{64}$", re.IGNORECASE)


@dataclass(frozen=True)
class ConfigReleaseHardeningIssue:
    """One scorecard-readable Phase 28.4 validation issue."""

    code: str
    message: str
    field: str
    evidence_ref: str | None = None

    def as_gate_fields(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "evidence_ref": self.evidence_ref,
        }


def validate_config_release_deployment_migration_hardening_record(
    record: Mapping[str, Any] | None,
) -> list[ConfigReleaseHardeningIssue]:
    """Validate Phase 28.4 hardening evidence bound into a Policy Design Case."""

    if not isinstance(record, Mapping):
        return [
            _issue(
                "policy_design_config_release_hardening_record_missing",
                "Policy Design Case requires Phase 28.4 config/release hardening evidence.",
                "config_release_deployment_migration_hardening",
            )
        ]

    evidence_ref = _text(record.get("evidence_ref") or record.get("cas_ref"))
    issues: list[ConfigReleaseHardeningIssue] = []
    if record.get("schema_version") != CONFIG_RELEASE_HARDENING_SCHEMA_VERSION:
        issues.append(
            _issue(
                "policy_design_config_release_hardening_schema_invalid",
                "Config/release hardening record must use the Phase 28.4 schema.",
                "schema_version",
                evidence_ref,
            )
        )
    if record.get("record_family") != CONFIG_RELEASE_HARDENING_RECORD_FAMILY:
        issues.append(
            _issue(
                "policy_design_config_release_hardening_family_invalid",
                "Config/release hardening must bind to publication trust governance.",
                "record_family",
                evidence_ref,
            )
        )
    if _status(record.get("status")) not in _PASS_STATUSES:
        issues.append(
            _issue(
                "policy_design_config_release_hardening_status_not_pass",
                "Config/release hardening record must be passing for serious closeout.",
                "status",
                evidence_ref,
            )
        )
    for field in ("record_id", "contract_id", "run_id"):
        if not _text(record.get(field)):
            issues.append(
                _issue(
                    "policy_design_config_release_hardening_identity_missing",
                    "Config/release hardening record must include case-bound identity fields.",
                    field,
                    evidence_ref,
                )
            )
    if _text(record.get("contract_id")) and (
        record.get("contract_id") != CONFIG_RELEASE_HARDENING_CONTRACT_ID
    ):
        issues.append(
            _issue(
                "policy_design_config_release_hardening_identity_invalid",
                "Config/release hardening record must use the Phase 28.4 contract id.",
                "contract_id",
                evidence_ref,
            )
        )
    issues.extend(_pdd_coverage_issues(record, evidence_ref=evidence_ref))
    issues.extend(_authority_ref_issues(record, evidence_ref=evidence_ref))
    issues.extend(_deployment_parity_issues(record.get("deployment_parity"), evidence_ref))
    issues.extend(_release_supply_chain_issues(record.get("release_supply_chain"), evidence_ref))
    issues.extend(
        _persisted_state_migration_issues(
            record.get("persisted_state_migration"),
            evidence_ref,
        )
    )
    issues.extend(
        _quarantine_shim_lifecycle_issues(
            record.get("quarantine_shim_lifecycle"),
            evidence_ref,
        )
    )
    issues.extend(
        _generated_surface_drift_issues(
            record.get("generated_surface_drift"),
            evidence_ref,
        )
    )
    issues.extend(_runbook_automation_issues(record.get("runbook_automation"), evidence_ref))
    issues.extend(
        _retention_deletion_replay_issues(
            record.get("retention_deletion_replay"),
            evidence_ref,
        )
    )
    return issues


def _pdd_coverage_issues(
    record: Mapping[str, Any],
    *,
    evidence_ref: str | None,
) -> list[ConfigReleaseHardeningIssue]:
    present = {_text(value) for value in _text_values(record.get("pdd_ids"))}
    missing = [pdd_id for pdd_id in CONFIG_RELEASE_HARDENING_PDD_IDS if pdd_id not in present]
    if not missing:
        return []
    return [
        _issue(
            "policy_design_config_release_hardening_pdd_missing",
            "Phase 28.4 record must name every config/release hardening PDD.",
            "pdd_ids",
            evidence_ref,
        )
    ]


def _authority_ref_issues(
    record: Mapping[str, Any],
    *,
    evidence_ref: str | None,
) -> list[ConfigReleaseHardeningIssue]:
    issues: list[ConfigReleaseHardeningIssue] = []
    if not _runtime_artifact_ref(record.get("evidence_ref") or record.get("cas_ref")):
        issues.append(
            _issue(
                "policy_design_config_release_hardening_runtime_ref_missing",
                "Phase 28.4 record must carry a runtime artifact ref.",
                "evidence_ref",
                evidence_ref,
            )
        )
    if not _runtime_event_ref(record.get("runtime_event_ref")):
        issues.append(
            _issue(
                "policy_design_config_release_hardening_runtime_event_missing",
                "Phase 28.4 record must carry a runtime event ref.",
                "runtime_event_ref",
                evidence_ref,
            )
        )
    return issues


def _deployment_parity_issues(
    payload: object,
    evidence_ref: str | None,
) -> list[ConfigReleaseHardeningIssue]:
    if not isinstance(payload, Mapping):
        return [
            _issue(
                "policy_design_deployment_parity_missing",
                "PDD-072 requires deployment topology and environment parity evidence.",
                "deployment_parity",
                evidence_ref,
            )
        ]
    issues: list[ConfigReleaseHardeningIssue] = []
    if not _text_values(payload.get("deployment_unit_refs")):
        issues.append(
            _issue(
                "policy_design_deployment_parity_ref_missing",
                "PDD-072 requires deployment-unit refs.",
                "deployment_parity.deployment_unit_refs",
                evidence_ref,
            )
        )
    observed_services = {
        _service_key(row.get("service"))
        for row in _mapping_rows(payload.get("required_service_matrix"))
    }
    if not observed_services >= REQUIRED_DEPLOYMENT_SERVICES:
        issues.append(
            _issue(
                "policy_design_deployment_parity_service_missing",
                "PDD-072 requires local/staging/production service parity evidence.",
                "deployment_parity.required_service_matrix",
                evidence_ref,
            )
        )
    for row in _mapping_rows(payload.get("required_service_matrix")):
        if not _service_row_has_real_lanes(row):
            issues.append(
                _issue(
                    "policy_design_deployment_parity_service_missing",
                    "Deployment services must be real or production-equivalent in every lane.",
                    "deployment_parity.required_service_matrix",
                    evidence_ref,
                )
            )
            break
    parity_diff = payload.get("parity_diff")
    if not isinstance(parity_diff, Mapping) or _status(parity_diff.get("status")) not in (
        _PASS_STATUSES
    ):
        issues.append(
            _issue(
                "policy_design_deployment_parity_mismatch",
                "Deployment parity diff must pass or match.",
                "deployment_parity.parity_diff",
                evidence_ref,
            )
        )
    if not _runtime_artifact_ref(payload.get("topology_ref")):
        issues.append(
            _issue(
                "policy_design_deployment_parity_ref_missing",
                "PDD-072 requires topology evidence.",
                "deployment_parity.topology_ref",
                evidence_ref,
            )
        )
    if not _text_values(payload.get("promotion_gate_refs")):
        issues.append(
            _issue(
                "policy_design_deployment_parity_ref_missing",
                "PDD-072 requires promotion-gate evidence.",
                "deployment_parity.promotion_gate_refs",
                evidence_ref,
            )
        )
    return issues


def _release_supply_chain_issues(
    payload: object,
    evidence_ref: str | None,
) -> list[ConfigReleaseHardeningIssue]:
    if not isinstance(payload, Mapping):
        return [
            _issue(
                "policy_design_release_provenance_missing",
                "PDD-075 requires release and supply-chain provenance.",
                "release_supply_chain",
                evidence_ref,
            )
        ]
    issues: list[ConfigReleaseHardeningIssue] = []
    for field in (
        "release_provenance_ref",
        "sbom_ref",
        "attestation_ref",
        "signing_ref",
    ):
        if not _runtime_artifact_ref(payload.get(field)):
            issues.append(
                _issue(
                    "policy_design_release_provenance_ref_missing",
                    "PDD-075 requires release provenance, SBOM, attestation, and signing refs.",
                    f"release_supply_chain.{field}",
                    evidence_ref,
                )
            )
    if not isinstance(payload.get("lockfile_fingerprints"), Mapping) or not payload.get(
        "lockfile_fingerprints"
    ):
        issues.append(
            _issue(
                "policy_design_release_provenance_ref_missing",
                "PDD-075 requires lockfile fingerprints.",
                "release_supply_chain.lockfile_fingerprints",
                evidence_ref,
            )
        )
    if not isinstance(
        payload.get("generated_artifact_fingerprints"),
        Mapping,
    ) or not payload.get("generated_artifact_fingerprints"):
        issues.append(
            _issue(
                "policy_design_release_provenance_ref_missing",
                "PDD-075 requires generated artifact fingerprints.",
                "release_supply_chain.generated_artifact_fingerprints",
                evidence_ref,
            )
        )
    if payload.get("dirty_tree_clean") is not True:
        issues.append(
            _issue(
                "policy_design_release_provenance_dirty_tree",
                "PDD-075 blocks production closeout on dirty-tree release provenance.",
                "release_supply_chain.dirty_tree_clean",
                evidence_ref,
            )
        )
    if _int(payload.get("untracked_artifact_count")) > 0:
        issues.append(
            _issue(
                "policy_design_release_untracked_artifacts",
                "PDD-075 blocks untracked release artifacts.",
                "release_supply_chain.untracked_artifact_count",
                evidence_ref,
            )
        )
    return issues


def _persisted_state_migration_issues(
    payload: object,
    evidence_ref: str | None,
) -> list[ConfigReleaseHardeningIssue]:
    if not isinstance(payload, Mapping):
        return [
            _issue(
                "policy_design_persisted_state_migration_missing",
                "PDD-076 requires persisted-state migration compatibility evidence.",
                "persisted_state_migration",
                evidence_ref,
            )
        ]
    issues: list[ConfigReleaseHardeningIssue] = []
    if not _text_values(payload.get("migration_exercise_refs")):
        issues.append(
            _issue(
                "policy_design_persisted_state_migration_ref_missing",
                "PDD-076 requires migration exercise bundle refs.",
                "persisted_state_migration.migration_exercise_refs",
                evidence_ref,
            )
        )
    if not _text_values(payload.get("compatibility_fixture_refs")):
        issues.append(
            _issue(
                "policy_design_persisted_state_migration_ref_missing",
                "PDD-076 requires persisted-state compatibility fixtures.",
                "persisted_state_migration.compatibility_fixture_refs",
                evidence_ref,
            )
        )
    checks = _mapping_rows(payload.get("historical_decision_checks"))
    if not checks:
        issues.append(
            _issue(
                "policy_design_persisted_state_migration_check_missing",
                "PDD-076 requires historical read/replay/reissue/withdraw checks.",
                "persisted_state_migration.historical_decision_checks",
                evidence_ref,
            )
        )
    for check in checks:
        for field in (
            "read_status",
            "replay_status",
            "migrate_status",
            "reissue_status",
            "withdraw_status",
        ):
            if _status(check.get(field)) not in _PASS_STATUSES:
                issues.append(
                    _issue(
                        "policy_design_persisted_state_migration_check_failed",
                        (
                            "PDD-076 blocks artifacts that cannot be read, replayed, "
                            "migrated, reissued, and withdrawn."
                        ),
                        f"persisted_state_migration.historical_decision_checks.{field}",
                        evidence_ref,
                    )
                )
                return issues
    return issues


def _quarantine_shim_lifecycle_issues(
    payload: object,
    evidence_ref: str | None,
) -> list[ConfigReleaseHardeningIssue]:
    if not isinstance(payload, Mapping):
        return [
            _issue(
                "policy_design_quarantine_shim_lifecycle_missing",
                "PDD-079 requires quarantine, deprecation, and shim lifecycle evidence.",
                "quarantine_shim_lifecycle",
                evidence_ref,
            )
        ]
    if not _runtime_artifact_ref(payload.get("ledger_ref")):
        return [
            _issue(
                "policy_design_quarantine_shim_ledger_missing",
                "PDD-079 requires a quarantine/deprecation/shim ledger ref.",
                "quarantine_shim_lifecycle.ledger_ref",
                evidence_ref,
            )
        ]
    if _text_values(payload.get("expired_usage_ids")):
        return [
            _issue(
                "policy_design_quarantine_shim_expired",
                "PDD-079 blocks expired quarantines, deprecated connectors, and stale shims.",
                "quarantine_shim_lifecycle.expired_usage_ids",
                evidence_ref,
            )
        ]
    if _text_values(payload.get("active_usage_ids")) and not _text_values(
        payload.get("approved_exception_refs")
    ):
        return [
            _issue(
                "policy_design_quarantine_shim_exception_missing",
                "PDD-079 requires signed production-safe exceptions for active shim usage.",
                "quarantine_shim_lifecycle.approved_exception_refs",
                evidence_ref,
            )
        ]
    return []


def _generated_surface_drift_issues(
    payload: object,
    evidence_ref: str | None,
) -> list[ConfigReleaseHardeningIssue]:
    if not isinstance(payload, Mapping):
        return [
            _issue(
                "policy_design_generated_surface_drift_record_missing",
                "PDD-080 requires generated-surface drift evidence.",
                "generated_surface_drift",
                evidence_ref,
            )
        ]
    issues: list[ConfigReleaseHardeningIssue] = []
    fingerprints = payload.get("fingerprints")
    present = set(fingerprints) if isinstance(fingerprints, Mapping) else set()
    if not present >= REQUIRED_GENERATED_SURFACES:
        issues.append(
            _issue(
                "policy_design_generated_surface_fingerprint_missing",
                "PDD-080 requires OpenAPI, client, dashboard, CLI, docs, and release fingerprints.",
                "generated_surface_drift.fingerprints",
                evidence_ref,
            )
        )
    diff = payload.get("runtime_to_generated_diff")
    if not isinstance(diff, Mapping) or _status(diff.get("status")) not in _PASS_STATUSES:
        issues.append(
            _issue(
                "policy_design_generated_surface_drift",
                "PDD-080 blocks runtime fields or statuses missing from generated surfaces.",
                "generated_surface_drift.runtime_to_generated_diff",
                evidence_ref,
            )
        )
    if not _text_values(payload.get("negative_consumer_test_refs")):
        issues.append(
            _issue(
                "policy_design_generated_surface_consumer_tests_missing",
                "PDD-080 requires negative consumer compatibility tests.",
                "generated_surface_drift.negative_consumer_test_refs",
                evidence_ref,
            )
        )
    return issues


def _runbook_automation_issues(
    payload: object,
    evidence_ref: str | None,
) -> list[ConfigReleaseHardeningIssue]:
    if not isinstance(payload, Mapping):
        return [
            _issue(
                "policy_design_runbook_automation_missing",
                "PDD-081 requires manual gate and runbook automation evidence.",
                "runbook_automation",
                evidence_ref,
            )
        ]
    issues: list[ConfigReleaseHardeningIssue] = []
    if not _runtime_artifact_ref(payload.get("manual_gate_inventory_ref")):
        issues.append(
            _issue(
                "policy_design_manual_gate_inventory_missing",
                "PDD-081 requires a manual-gate inventory ref.",
                "runbook_automation.manual_gate_inventory_ref",
                evidence_ref,
            )
        )
    for gate in _mapping_rows(payload.get("manual_gates")):
        gate_status = _status(gate.get("status"))
        if gate_status in {"stale", "fail", "failed"}:
            issues.append(
                _issue(
                    "policy_design_manual_gate_stale",
                    "PDD-081 blocks stale or failed manual gates.",
                    "runbook_automation.manual_gates.status",
                    evidence_ref,
                )
            )
            return issues
        if gate_status == "pass" and not _runtime_artifact_ref(gate.get("signed_review_ref")):
            issues.append(
                _issue(
                    "policy_design_manual_gate_signed_review_missing",
                    "PDD-081 requires signed review evidence for passing manual gates.",
                    "runbook_automation.manual_gates.signed_review_ref",
                    evidence_ref,
                )
            )
            return issues
    if _text_values(payload.get("stale_manual_gate_ids")):
        issues.append(
            _issue(
                "policy_design_manual_gate_stale",
                "PDD-081 blocks stale manual gate ids.",
                "runbook_automation.stale_manual_gate_ids",
                evidence_ref,
            )
        )
    return issues


def _retention_deletion_replay_issues(
    payload: object,
    evidence_ref: str | None,
) -> list[ConfigReleaseHardeningIssue]:
    if not isinstance(payload, Mapping):
        return [
            _issue(
                "policy_design_retention_deletion_replay_missing",
                "PDD-082 requires retention, deletion, replay, and auditability evidence.",
                "retention_deletion_replay",
                evidence_ref,
            )
        ]
    issues: list[ConfigReleaseHardeningIssue] = []
    for field in (
        "retention_replay_matrix_ref",
        "public_private_auditability_ref",
        "replay_evidence_ref",
    ):
        if not _runtime_artifact_ref(payload.get(field)):
            issues.append(
                _issue(
                    "policy_design_retention_deletion_replay_ref_missing",
                    "PDD-082 requires retention/replay and auditability refs.",
                    f"retention_deletion_replay.{field}",
                    evidence_ref,
                )
            )
    if not _text_values(payload.get("deletion_minimization_scenario_refs")):
        issues.append(
            _issue(
                "policy_design_retention_deletion_replay_ref_missing",
                "PDD-082 requires deletion/minimization scenarios.",
                "retention_deletion_replay.deletion_minimization_scenario_refs",
                evidence_ref,
            )
        )
    for blocker in _mapping_rows(payload.get("jurisdiction_blockers")):
        if _status(blocker.get("status")) in _ACTIVE_BLOCKER_STATUSES:
            issues.append(
                _issue(
                    "policy_design_retention_deletion_replay_conflict",
                    "PDD-082 blocks retention/deletion/replay conflicts.",
                    "retention_deletion_replay.jurisdiction_blockers",
                    evidence_ref,
                )
            )
            break
    return issues


def _service_row_has_real_lanes(row: Mapping[str, Any]) -> bool:
    acceptable = {"real", "production_equivalent", "equivalent", "pass"}
    return all(_status(row.get(lane)) in acceptable for lane in ("local", "staging", "production"))


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if not isinstance(value, Iterable) or isinstance(value, Mapping):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _runtime_artifact_ref(value: object) -> bool:
    text = _text(value)
    return bool(text and (_SHA_REF_RE.fullmatch(text) or text.startswith("cas://")))


def _runtime_event_ref(value: object) -> bool:
    text = _text(value)
    return bool(text and (text.startswith("event://") or _runtime_artifact_ref(text)))


def _status(value: object) -> str:
    return _text(value).casefold().replace("-", "_")


def _service_key(value: object) -> str:
    return _status(value)


def _int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(value: object) -> str:
    return str(value or "").strip()


def _issue(
    code: str,
    message: str,
    field: str,
    evidence_ref: str | None = None,
) -> ConfigReleaseHardeningIssue:
    return ConfigReleaseHardeningIssue(
        code=code,
        message=message,
        field=field,
        evidence_ref=evidence_ref,
    )


__all__ = [
    "CONFIG_RELEASE_HARDENING_CONTRACT_ID",
    "CONFIG_RELEASE_HARDENING_PDD_IDS",
    "CONFIG_RELEASE_HARDENING_RECORD_FAMILY",
    "CONFIG_RELEASE_HARDENING_SCHEMA_VERSION",
    "ConfigReleaseHardeningIssue",
    "validate_config_release_deployment_migration_hardening_record",
]
