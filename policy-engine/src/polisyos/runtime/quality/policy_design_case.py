"""Minimum Policy Design Case record-family registry.

The registry is the runtime-readable contract for the SDD minimum record
families. It does not make future producer evidence pass early; it names the
owner, schema, reader gate, readiness hook, and current enforcement function
that must block or explain each family until the owning producer emits runtime
evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]

RECORD_REGISTRY_SCHEMA_VERSION = "policyos.policy_design_case.record_registry.v1"
RECORD_REGISTRY_VALIDATION_SCHEMA_VERSION = (
    "policyos.policy_design_case.record_registry.validation.v1"
)
TOOL_NAME = "runtime.quality.policy-design-case-record-registry"
DEFAULT_NEXT_DIAGNOSTIC_COMMAND = (
    "uv run pytest tests/unit/runtime/quality/test_policy_design_case_record_registry.py "
    "tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q"
)
RECORD_REGISTRY_ENFORCEMENT_FUNCTION = (
    "polisyos.runtime.quality.policy_design_case."
    "validate_policy_design_case_record_registry_payload"
)
RECORD_REGISTRY_READINESS_CHECK = "policy_design_case.minimum_record_registry"
RECORD_REGISTRY_SCORECARD_GATE = "policy_design_case.minimum_record_registry"
SUBSTRATE_RESIDUAL_BINDINGS_SCHEMA_VERSION = (
    "policyos.policy_design_case.substrate_residual_bindings.v1"
)
SUBSTRATE_RESIDUAL_BINDINGS_READINESS_CHECK = "policy_design_case.substrate_residual_bindings"
SUBSTRATE_RESIDUAL_BINDINGS_SCORECARD_GATE = (
    "policy_design_case.substrate_residual_bindings.present_or_blocked"
)
SUBSTRATE_RESIDUAL_BINDINGS_ENFORCEMENT_FUNCTION = (
    "polisyos.runtime.quality.policy_design_case."
    "validate_policy_design_case_substrate_residual_bindings"
)
SUBSTRATE_RESIDUAL_BINDINGS_NEXT_DIAGNOSTIC_COMMAND = (
    "uv run pytest tests/unit/runtime/quality/test_policy_design_case_record_registry.py "
    "tests/unit/runtime/quality/test_effective_mode.py "
    "tests/unit/runtime/quality/test_replay.py "
    "tests/repo_quality/tools/test_runtime_resilience_matrix.py "
    "tests/unit/runtime/quality/test_authority_spoofing.py "
    "tests/unit/runtime/quality/test_crash_retry_partial_state.py "
    "tests/unit/runtime/quality/test_multi_tenant_shared_cas.py "
    "tests/unit/runtime/quality/test_public_export.py "
    "tests/unit/runtime/quality/test_prompt_tool_ledger.py -q"
)
SUBSTRATE_RESIDUAL_VERIFICATION_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.substrate_residual_verification.v1"
)
SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_KEY = "substrate_residual_verification"
SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_FAMILY = "substrate_residual_verification.v1"
SUBSTRATE_RESIDUAL_VERIFICATION_NEXT_ACTION = (
    "Emit the Phase 28.2 substrate-residual verification record with PDD-bound "
    "runtime evidence refs before serious closeout."
)
SUBSTRATE_RESIDUAL_PASSING_STATUSES = frozenset(
    {"pass", "passed", "ok", "accepted", "approved", "verified"}
)
POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_DIAGNOSTICS = (
    "PDD-019",
    "PDD-031",
    "PDD-032",
    "PDD-039",
    "PDD-040",
    "PDD-041",
    "PDD-067",
    "PDD-071",
    "PDD-084",
    "PDD-086",
)

POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES = (
    "intent_authoring_and_capture_risk.v1",
    "capability_mode_and_fallback_selection.v1",
    "concept_and_jurisdiction_spine.v1",
    "legal_authority_and_competence.v1",
    "data_source_semantic_lineage.v1",
    "scholar_academic_evidence.v1",
    "numeric_time_and_geography_semantics.v1",
    "method_selection_and_validity.v1",
    "evidence_portfolio_and_synthesis.v1",
    "structured_judgement_and_consultation.v1",
    "options_objectives_and_tradeoffs.v1",
    "claim_argument_evidence_case.v1",
    "implementation_monitoring_and_evaluation.v1",
    "human_oversight_independence_and_review.v1",
    "integrity_self_fmea_and_maturity.v1",
    "lifecycle_ex_post_and_calibration.v1",
    "publication_trust_and_external_governance.v1",
    "best_in_class_benchmarking.v1",
    "formal_substrate_invariant_spec.v1",
)

RECORD_FAMILY_COVERAGE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.record_family_coverage.v1"
)
RUNTIME_RECORD_FAMILY_COMPILATION_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.record_family_compilation.v1"
)
RECORD_FAMILY_COVERAGE_SCORECARD_GATE = "policy_design_case.record_family_coverage"
RECORD_FAMILY_COVERAGE_READINESS_CHECK = "policy_design_case.record_family_coverage"
RECORD_FAMILY_COVERAGE_NEXT_ACTION = (
    "Emit concrete Policy Design Case records and record_families with schema owner, "
    "producer owner, reader owner, readiness gate, runtime refs, and authority envelope "
    "for every minimum SDD family before serious closeout."
)
POLICY_DESIGN_CASE_RECORD_FAMILY_PRESENT_STATUSES = frozenset(
    {"pass", "passed", "ok", "present", "implemented", "accepted", "complete"}
)
POLICY_DESIGN_CASE_RECORD_FAMILY_POLICY_STATUSES = frozenset(
    {"blocked", "out_of_scope", "not_applicable"}
)
POLICY_DESIGN_CASE_GOVERNANCE_RECORD_FAMILY_REQUIREMENTS = {
    "structured_judgement": "structured_judgement_and_consultation.v1",
    "consultation": "structured_judgement_and_consultation.v1",
    "implementation_monitoring": "implementation_monitoring_and_evaluation.v1",
    "ddm": "implementation_monitoring_and_evaluation.v1",
    "human_oversight": "human_oversight_independence_and_review.v1",
    "self_fmea": "integrity_self_fmea_and_maturity.v1",
    "maturity": "integrity_self_fmea_and_maturity.v1",
    "audit": "publication_trust_and_external_governance.v1",
    "benchmarking": "best_in_class_benchmarking.v1",
    "proportionality": "best_in_class_benchmarking.v1",
    "formal_invariants": "formal_substrate_invariant_spec.v1",
}

KNOWN_RECORD_REGISTRY_READINESS_CHECKS = frozenset(
    {
        RECORD_REGISTRY_READINESS_CHECK,
    }
)
KNOWN_RECORD_REGISTRY_ENFORCEMENT_FUNCTIONS = frozenset(
    {
        RECORD_REGISTRY_ENFORCEMENT_FUNCTION,
    }
)


class PolicyDesignCaseRecordApplicability(StrEnum):
    """Applicability classification for one SDD minimum record family."""

    REQUIRED = "required"
    PROFILE_SCOPED = "profile_scoped"
    NOT_APPLICABLE = "not_applicable"


class PolicyDesignCaseApplicabilityEvidenceKind(StrEnum):
    """Typed evidence source for a registry applicability decision."""

    SDD_MINIMUM_RECORD_FAMILY = "sdd_minimum_record_family"
    AUTHORITY_PROFILE_SCOPE = "authority_profile_scope"
    ACCEPTED_NOT_APPLICABLE_DECISION = "accepted_not_applicable_decision"


@dataclass(frozen=True)
class PolicyDesignCaseApplicabilityEvidence:
    """Typed evidence explaining why a family is required or profile-scoped."""

    kind: PolicyDesignCaseApplicabilityEvidenceKind
    source: str
    reason: str
    profiles: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "source": self.source,
            "reason": self.reason,
            "profiles": list(self.profiles),
        }


@dataclass(frozen=True)
class PolicyDesignCaseRecordFamily:
    """Typed view of one minimum Policy Design Case record-family row."""

    family_id: str
    title: str
    applicability: PolicyDesignCaseRecordApplicability
    applicability_evidence: PolicyDesignCaseApplicabilityEvidence
    producer_owner: str
    reader_owner: str
    schema_name: str
    scorecard_gate: str
    readiness_check: str
    enforcement_function: str
    next_diagnostic_command: str
    maturity_floor: str
    sdd_facets: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "title": self.title,
            "applicability": self.applicability.value,
            "applicability_evidence": self.applicability_evidence.as_dict(),
            "producer_owner": self.producer_owner,
            "reader_owner": self.reader_owner,
            "schema_name": self.schema_name,
            "scorecard_gate": self.scorecard_gate,
            "readiness_check": self.readiness_check,
            "enforcement_function": self.enforcement_function,
            "next_diagnostic_command": self.next_diagnostic_command,
            "maturity_floor": self.maturity_floor,
            "sdd_facets": list(self.sdd_facets),
        }


@dataclass(frozen=True)
class PolicyDesignCaseSubstrateResidualBinding:
    """Typed PDD-to-record binding for substrate residual verification."""

    binding_id: str
    diagnostic_id: str
    title: str
    record_family_id: str
    record_facets: tuple[str, ...]
    runtime_records: tuple[str, ...]
    scorecard_gate: str
    readiness_check: str
    enforcement_function: str
    test_paths: tuple[str, ...]
    next_diagnostic_command: str
    owner: str = "team-runtime-quality"

    def as_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "diagnostic_id": self.diagnostic_id,
            "title": self.title,
            "record_family_id": self.record_family_id,
            "record_facets": list(self.record_facets),
            "runtime_records": list(self.runtime_records),
            "scorecard_gate": self.scorecard_gate,
            "readiness_check": self.readiness_check,
            "enforcement_function": self.enforcement_function,
            "test_paths": list(self.test_paths),
            "next_diagnostic_command": self.next_diagnostic_command,
            "owner": self.owner,
        }


@dataclass(frozen=True)
class PolicyDesignCaseRecordRegistryIssue:
    """One deterministic minimum-record registry validation issue."""

    code: str
    family_id: str
    field: str
    message: str
    value: object | None = None
    severity: str = "error"

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "severity": self.severity,
            "family_id": self.family_id,
            "field": self.field,
            "message": self.message,
        }
        if self.value is not None:
            payload["value"] = self.value
        return payload


@dataclass(frozen=True)
class PolicyDesignCaseRecordRegistryValidationResult:
    """Validation result shared by scorecard, readiness, and tests."""

    status: str
    record_families: tuple[dict[str, Any], ...]
    issues: tuple[PolicyDesignCaseRecordRegistryIssue, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "summary": {
                "record_family_count": len(self.record_families),
                "issue_count": len(self.issues),
                "required_family_count": len(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES),
            },
            "record_families": list(self.record_families),
            "issues": [issue.as_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class PolicyDesignCaseRecordFamilyCoverageResult:
    """Validation result for concrete runtime Policy Design Case records."""

    status: str
    record_families: tuple[dict[str, Any], ...]
    records: tuple[dict[str, Any], ...]
    issues: tuple[PolicyDesignCaseRecordRegistryIssue, ...]

    def as_dict(self) -> dict[str, object]:
        governance_surfaces = {
            surface
            for row in self.record_families
            for surface in _string_list(row.get("governance_surfaces"))
        }
        return {
            "schema_version": RECORD_FAMILY_COVERAGE_SCHEMA_VERSION,
            "status": self.status,
            "summary": {
                "record_family_count": len(self.record_families),
                "runtime_record_count": len(self.records),
                "issue_count": len(self.issues),
                "required_family_count": len(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES),
                "governance_surface_count": len(governance_surfaces),
            },
            "record_families": list(self.record_families),
            "records": list(self.records),
            "issues": [issue.as_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class PolicyDesignCaseSubstrateResidualBindingValidationResult:
    """Validation result for Phase 28.2 substrate-residual bindings."""

    status: str
    bindings: tuple[dict[str, Any], ...]
    issues: tuple[PolicyDesignCaseRecordRegistryIssue, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "summary": {
                "binding_count": len(self.bindings),
                "issue_count": len(self.issues),
                "required_diagnostic_count": len(POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_DIAGNOSTICS),
            },
            "substrate_residual_bindings": list(self.bindings),
            "issues": [issue.as_dict() for issue in self.issues],
        }


def policy_design_case_record_registry_payload() -> dict[str, Any]:
    """Return the default minimum record-family registry payload."""

    rows = [row.as_dict() for row in DEFAULT_POLICY_DESIGN_CASE_RECORD_REGISTRY]
    substrate_bindings = [
        row.as_dict() for row in DEFAULT_POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_BINDINGS
    ]
    return {
        "schema_version": RECORD_REGISTRY_SCHEMA_VERSION,
        "substrate_residual_schema_version": SUBSTRATE_RESIDUAL_BINDINGS_SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "source": {
            "sdd": ("docs/system-design-decisions/policy-design-best-in-class-operating-model.md"),
            "plan_phase": "Wave 3 Phase 3.3; Wave 28 Phase 28.2",
        },
        "summary": {
            "record_family_count": len(rows),
            "required_family_count": len(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES),
            "substrate_residual_binding_count": len(substrate_bindings),
        },
        "record_families": rows,
        "substrate_residual_bindings": substrate_bindings,
    }


def validate_policy_design_case_record_registry_payload(
    payload: Mapping[str, Any] | None = None,
    *,
    known_readiness_checks: frozenset[str] | set[str] = KNOWN_RECORD_REGISTRY_READINESS_CHECKS,
    known_enforcement_functions: frozenset[str] | set[str] = (
        KNOWN_RECORD_REGISTRY_ENFORCEMENT_FUNCTIONS
    ),
) -> PolicyDesignCaseRecordRegistryValidationResult:
    """Validate that every SDD minimum family has owner and enforcement links."""

    source = policy_design_case_record_registry_payload() if payload is None else payload
    raw_rows = source.get("record_families") if isinstance(source, Mapping) else None
    issues: list[PolicyDesignCaseRecordRegistryIssue] = []
    rows: list[dict[str, Any]] = []
    schema_version = source.get("schema_version") if isinstance(source, Mapping) else None
    if schema_version != RECORD_REGISTRY_SCHEMA_VERSION:
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_record_registry_schema_version_invalid",
                family_id="registry",
                field="schema_version",
                message="Policy Design Case registry must use the current schema version.",
                value=schema_version,
            )
        )
    if not isinstance(raw_rows, list) or not raw_rows:
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_record_registry_missing_rows",
                family_id="registry",
                field="record_families",
                message="Policy Design Case registry must define record_families rows.",
            )
        )
        return PolicyDesignCaseRecordRegistryValidationResult(
            status="fail",
            record_families=(),
            issues=tuple(issues),
        )

    seen: dict[str, int] = {}
    for index, raw_row in enumerate(raw_rows, start=1):
        if not isinstance(raw_row, Mapping):
            issues.append(
                PolicyDesignCaseRecordRegistryIssue(
                    code="policy_design_case_record_family_row_invalid",
                    family_id=f"record_families[{index}]",
                    field="record_families",
                    message="Every Policy Design Case registry row must be an object.",
                )
            )
            continue
        row = dict(raw_row)
        rows.append(row)
        family_id = _row_family_id(row, index)
        if family_id in seen:
            issues.append(
                PolicyDesignCaseRecordRegistryIssue(
                    code="policy_design_case_record_family_duplicate",
                    family_id=family_id,
                    field="family_id",
                    message="Policy Design Case record family IDs must be unique.",
                    value=family_id,
                )
            )
        seen[family_id] = index
        issues.extend(
            _record_family_row_issues(
                row,
                index=index,
                known_readiness_checks=known_readiness_checks,
                known_enforcement_functions=known_enforcement_functions,
            )
        )

    expected = set(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES)
    actual = {
        str(row.get("family_id")).strip() for row in rows if _non_empty_string(row.get("family_id"))
    }
    for family_id in sorted(expected - actual):
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_record_family_missing",
                family_id=family_id,
                field="family_id",
                message="Every SDD minimum Policy Design Case family needs a registry row.",
                value=family_id,
            )
        )
    for family_id in sorted(actual - expected):
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_record_family_unknown",
                family_id=family_id,
                field="family_id",
                message="Registry row must reference an SDD minimum record family.",
                value=family_id,
            )
        )

    return PolicyDesignCaseRecordRegistryValidationResult(
        status="fail" if issues else "pass",
        record_families=tuple(rows),
        issues=tuple(issues),
    )


def build_policy_design_case_record_registry_report(
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a machine-readable registry validation report."""

    registry_payload = policy_design_case_record_registry_payload() if payload is None else payload
    result = validate_policy_design_case_record_registry_payload(registry_payload)
    substrate_result = validate_policy_design_case_substrate_residual_bindings(registry_payload)
    result_payload = result.as_dict()
    return {
        "schema_version": RECORD_REGISTRY_VALIDATION_SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "repo_root": str(REPO_ROOT),
        "source": dict(registry_payload.get("source", {}))
        if isinstance(registry_payload, Mapping)
        else {},
        **result_payload,
        "substrate_residual_binding_report": substrate_result.as_dict(),
        "catalogs": {
            "minimum_record_families": list(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES),
            "substrate_residual_diagnostics": list(
                POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_DIAGNOSTICS
            ),
            "readiness_checks": sorted(KNOWN_RECORD_REGISTRY_READINESS_CHECKS),
            "enforcement_functions": sorted(
                KNOWN_RECORD_REGISTRY_ENFORCEMENT_FUNCTIONS
                | {SUBSTRATE_RESIDUAL_BINDINGS_ENFORCEMENT_FUNCTION}
            ),
        },
    }


def validate_policy_design_case_substrate_residual_bindings(
    payload: Mapping[str, Any] | None = None,
) -> PolicyDesignCaseSubstrateResidualBindingValidationResult:
    """Validate Phase 28.2 residual PDD bindings against the case registry."""

    source = policy_design_case_record_registry_payload() if payload is None else payload
    raw_bindings = source.get("substrate_residual_bindings")
    if raw_bindings is None and source.get("schema_version") == (
        SUBSTRATE_RESIDUAL_BINDINGS_SCHEMA_VERSION
    ):
        raw_bindings = source.get("bindings")

    issues: list[PolicyDesignCaseRecordRegistryIssue] = []
    if source.get("substrate_residual_schema_version") not in {
        None,
        SUBSTRATE_RESIDUAL_BINDINGS_SCHEMA_VERSION,
    }:
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_substrate_residual_schema_version_invalid",
                family_id="substrate_residual_bindings",
                field="substrate_residual_schema_version",
                message=(
                    "Policy Design Case substrate-residual bindings must use the "
                    "current schema version."
                ),
                value=source.get("substrate_residual_schema_version"),
            )
        )
    if not isinstance(raw_bindings, list) or not raw_bindings:
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_substrate_residual_bindings_missing",
                family_id="substrate_residual_bindings",
                field="substrate_residual_bindings",
                message="Phase 28.2 substrate-residual bindings must be present.",
            )
        )
        return PolicyDesignCaseSubstrateResidualBindingValidationResult(
            status="fail",
            bindings=(),
            issues=tuple(issues),
        )

    record_families = _record_family_index(source)
    bindings: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for index, raw_binding in enumerate(raw_bindings, start=1):
        if not isinstance(raw_binding, Mapping):
            issues.append(
                PolicyDesignCaseRecordRegistryIssue(
                    code="policy_design_case_substrate_residual_binding_invalid",
                    family_id=f"substrate_residual_bindings[{index}]",
                    field="substrate_residual_bindings",
                    message="Every substrate-residual binding must be an object.",
                )
            )
            continue
        binding = dict(raw_binding)
        bindings.append(binding)
        diagnostic_id = _binding_diagnostic_id(binding, index)
        if diagnostic_id in seen:
            issues.append(
                PolicyDesignCaseRecordRegistryIssue(
                    code="policy_design_case_substrate_residual_binding_duplicate",
                    family_id=diagnostic_id,
                    field="diagnostic_id",
                    message="Substrate-residual diagnostic bindings must be unique.",
                    value=diagnostic_id,
                )
            )
        seen[diagnostic_id] = index
        issues.extend(
            _substrate_residual_binding_issues(
                binding,
                index=index,
                record_families=record_families,
            )
        )

    expected = set(POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_DIAGNOSTICS)
    actual = {
        str(binding.get("diagnostic_id")).strip()
        for binding in bindings
        if _non_empty_string(binding.get("diagnostic_id"))
    }
    for diagnostic_id in sorted(expected - actual):
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_substrate_residual_binding_missing",
                family_id=diagnostic_id,
                field="diagnostic_id",
                message="Every Phase 28.2 PDD must have a Policy Design Case binding.",
                value=diagnostic_id,
            )
        )
    for diagnostic_id in sorted(actual - expected):
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_substrate_residual_binding_unknown",
                family_id=diagnostic_id,
                field="diagnostic_id",
                message="Substrate-residual binding references an out-of-scope PDD.",
                value=diagnostic_id,
            )
        )

    return PolicyDesignCaseSubstrateResidualBindingValidationResult(
        status="fail" if issues else "pass",
        bindings=tuple(bindings),
        issues=tuple(issues),
    )


def policy_design_case_record_registry_scorecard_gates(
    *,
    registry_payload: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return scorecard gates for the static registry contract itself."""

    result = validate_policy_design_case_record_registry_payload(registry_payload)
    substrate_result = validate_policy_design_case_substrate_residual_bindings(
        registry_payload
    )
    issues = list(result.issues) + list(substrate_result.issues)
    if not issues:
        return []
    return [
        {
            "name": RECORD_REGISTRY_SCORECARD_GATE,
            "stage": "ops",
            "code": issue.code,
            "status": "fail",
            "layer": "policy_design_case_record_registry",
            "phase": "policy_design_case_record_registry",
            "message": issue.message,
            "evidence_ref": "src/polisyos/runtime/quality/policy_design_case.py",
            "next_action": DEFAULT_NEXT_DIAGNOSTIC_COMMAND,
            "blocking": True,
        }
        for issue in issues
    ]


def validate_policy_design_case_record_family_coverage(
    case: Mapping[str, Any] | None,
) -> PolicyDesignCaseRecordFamilyCoverageResult:
    """Validate concrete runtime records for every minimum SDD family."""

    if not isinstance(case, Mapping):
        issue = _coverage_issue(
            "policy_design_case_record_family_coverage_missing",
            "policy_design_case",
            "policy_design_case",
            "Policy Design Case runtime record-family coverage is missing.",
        )
        return PolicyDesignCaseRecordFamilyCoverageResult(
            status="fail",
            record_families=(),
            records=(),
            issues=(issue,),
        )

    raw_family_rows = case.get("record_families")
    raw_record_rows = case.get("records")
    family_rows = _case_record_family_rows(raw_family_rows)
    record_rows = _case_record_rows(raw_record_rows)
    issues: list[PolicyDesignCaseRecordRegistryIssue] = []

    if not family_rows:
        issues.append(
            _coverage_issue(
                "policy_design_case_record_families_missing",
                "record_families",
                "record_families",
                (
                    "Policy Design Case `status=pass` cannot replace concrete "
                    "record_families rows."
                ),
            )
        )
    if not record_rows:
        issues.append(
            _coverage_issue(
                "policy_design_case_records_missing",
                "records",
                "records",
                (
                    "Policy Design Case `status=pass` cannot replace concrete "
                    "runtime records."
                ),
            )
        )

    records_by_family: dict[str, list[dict[str, Any]]] = {}
    normalized_records: list[dict[str, Any]] = []
    for index, record in enumerate(record_rows, start=1):
        row = dict(record)
        family_id = _case_record_family_id(row, index)
        row["family_id"] = family_id
        normalized_records.append(row)
        records_by_family.setdefault(family_id, []).append(row)
        issues.extend(_case_runtime_record_issues(row, index=index))

    normalized_families: list[dict[str, Any]] = []
    seen_families: dict[str, int] = {}
    for index, family in enumerate(family_rows, start=1):
        row = dict(family)
        family_id = _case_family_row_id(row, index)
        row["family_id"] = family_id
        row.setdefault("status", "present")
        row["readiness_gate"] = _text_field(
            row.get("readiness_gate") or row.get("readiness_check")
        )
        row["runtime_record_count"] = len(records_by_family.get(family_id, []))
        row["authority_status"] = _case_family_authority_status(
            row,
            records_by_family.get(family_id, []),
        )
        if family_id in seen_families:
            issues.append(
                _coverage_issue(
                    "policy_design_case_record_family_duplicate",
                    family_id,
                    "family_id",
                    "Policy Design Case record_families rows must be unique.",
                    value=family_id,
                )
            )
        seen_families[family_id] = index
        issues.extend(
            _case_record_family_coverage_issues(
                row,
                records_by_family.get(family_id, []),
                index=index,
            )
        )
        normalized_families.append(row)

    expected = set(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES)
    actual = {
        row["family_id"]
        for row in normalized_families
        if _non_empty_string(row.get("family_id"))
    }
    for family_id in sorted(expected - actual):
        issues.append(
            _coverage_issue(
                "policy_design_case_record_family_missing",
                family_id,
                "record_families.family_id",
                "Every minimum SDD Policy Design Case family needs a runtime row.",
                value=family_id,
            )
        )
    for family_id in sorted(actual - expected):
        issues.append(
            _coverage_issue(
                "policy_design_case_record_family_unknown",
                family_id,
                "record_families.family_id",
                "Runtime record_families rows must reference minimum SDD families.",
                value=family_id,
            )
        )
    for family_id in sorted(set(records_by_family) - expected):
        issues.append(
            _coverage_issue(
                "policy_design_case_runtime_record_family_unknown",
                family_id,
                "records.family_id",
                "Runtime records must bind to minimum SDD record families.",
                value=family_id,
            )
        )

    family_by_id = {row["family_id"]: row for row in normalized_families}
    for surface, family_id in POLICY_DESIGN_CASE_GOVERNANCE_RECORD_FAMILY_REQUIREMENTS.items():
        row = family_by_id.get(family_id)
        if not row:
            continue
        surfaces = set(_string_list(row.get("governance_surfaces")))
        if surface not in surfaces:
            issues.append(
                _coverage_issue(
                    "policy_design_case_governance_surface_missing",
                    family_id,
                    "governance_surfaces",
                    (
                        "Governance SDD surfaces must be explicitly present, blocked, "
                        "or out-of-scope by typed authority policy."
                    ),
                    value=surface,
                )
            )

    return PolicyDesignCaseRecordFamilyCoverageResult(
        status="fail" if issues else "pass",
        record_families=tuple(normalized_families),
        records=tuple(normalized_records),
        issues=tuple(issues),
    )


def build_policy_design_case_record_family_coverage_report(
    case: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a machine-readable concrete record-family coverage report."""

    return validate_policy_design_case_record_family_coverage(case).as_dict()


def policy_design_case_record_family_coverage_scorecard_gates(
    case: Mapping[str, Any],
    *,
    phase: str = "policy_design_case_record_family_coverage",
    gate_name: str = RECORD_FAMILY_COVERAGE_SCORECARD_GATE,
) -> list[dict[str, Any]]:
    """Return scorecard gates for concrete runtime PDC record-family coverage."""

    result = validate_policy_design_case_record_family_coverage(case)
    return [
        {
            "name": gate_name,
            "stage": "ops",
            "code": issue.code,
            "status": "fail",
            "layer": "assurance_case",
            "phase": phase,
            "message": issue.message,
            "evidence_ref": "quality_evidence/policy_design_case.json",
            "next_action": RECORD_FAMILY_COVERAGE_NEXT_ACTION,
            "missing_input": issue.field,
            "family_id": issue.family_id,
            "blocking": True,
        }
        for issue in result.issues
    ]


def validate_policy_design_case_substrate_residual_verification_record(
    record: Mapping[str, Any] | None,
) -> tuple[PolicyDesignCaseRecordRegistryIssue, ...]:
    """Validate the Phase 28.2 case-bound substrate-residual evidence record."""

    if not isinstance(record, Mapping):
        return (
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_substrate_residual_verification_record_missing",
                family_id=SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_KEY,
                field=SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_KEY,
                message=(
                    "Policy Design Case requires the Phase 28.2 substrate-residual "
                    "verification record."
                ),
            ),
        )
    issues: list[PolicyDesignCaseRecordRegistryIssue] = []
    evidence_ref = str(record.get("evidence_ref") or record.get("cas_ref") or "")
    if record.get("schema_version") != SUBSTRATE_RESIDUAL_VERIFICATION_SCHEMA_VERSION:
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_schema_invalid",
                "schema_version",
                "Substrate-residual verification record must use the current schema.",
                value=record.get("schema_version"),
            )
        )
    if record.get("record_family") != SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_FAMILY:
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_family_invalid",
                "record_family",
                "Substrate-residual verification must be an independent record family.",
                value=record.get("record_family"),
            )
        )
    if _status(record.get("status")) not in SUBSTRATE_RESIDUAL_PASSING_STATUSES:
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_status_not_pass",
                "status",
                "Substrate-residual verification record must be passing.",
                value=record.get("status"),
            )
        )
    for field in ("record_id", "case_id", "run_id", "job_id", "tenant_id"):
        if not _non_empty_string(record.get(field)):
            issues.append(
                _substrate_verification_issue(
                    "policy_design_substrate_residual_verification_identity_missing",
                    field,
                    "Substrate-residual verification record must include case-bound identity.",
                )
            )
    if not _runtime_artifact_ref(record.get("evidence_ref") or record.get("cas_ref")):
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_runtime_ref_missing",
                "evidence_ref",
                "Substrate-residual verification record must include runtime evidence.",
                value=evidence_ref or None,
            )
        )
    if not _runtime_event_ref(record.get("runtime_event_ref")):
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_runtime_event_missing",
                "runtime_event_ref",
                "Substrate-residual verification record must include a runtime event.",
                value=record.get("runtime_event_ref"),
            )
        )

    bindings = _mapping_rows(
        record.get("pdd_bindings") or record.get("substrate_residual_bindings")
    )
    by_diagnostic: dict[str, list[Mapping[str, Any]]] = {}
    for row in bindings:
        diagnostic_id = row.get("diagnostic_id") or row.get("pdd_id")
        if _non_empty_string(diagnostic_id):
            by_diagnostic.setdefault(str(diagnostic_id).strip(), []).append(row)

    expected_bindings = {
        binding.diagnostic_id: binding
        for binding in DEFAULT_POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_BINDINGS
    }
    for diagnostic_id in POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_DIAGNOSTICS:
        rows = by_diagnostic.get(diagnostic_id, [])
        if not rows:
            issues.append(
                _substrate_verification_issue(
                    "policy_design_substrate_residual_verification_pdd_missing",
                    "pdd_bindings",
                    "Every Phase 28.2 PDD must be represented in the case-bound record.",
                    family_id=diagnostic_id,
                    value=diagnostic_id,
                )
            )
            continue
        for row in rows:
            issues.extend(
                _substrate_verification_binding_issues(
                    row,
                    expected=expected_bindings[diagnostic_id],
                )
            )
    for diagnostic_id in sorted(set(by_diagnostic) - set(expected_bindings)):
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_pdd_unknown",
                "pdd_bindings",
                "Substrate-residual verification references an out-of-scope PDD.",
                family_id=diagnostic_id,
                value=diagnostic_id,
            )
        )
    return tuple(issues)


def policy_design_case_substrate_residual_verification_scorecard_gates(
    case: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return scorecard gates for the Phase 28.2 case-bound record."""

    record = case.get(SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_KEY)
    issues = validate_policy_design_case_substrate_residual_verification_record(
        record if isinstance(record, Mapping) else None
    )
    return [
        {
            "name": "policy_design_substrate_residual_verification",
            "stage": "ops",
            "code": issue.code,
            "status": "fail",
            "layer": "assurance_case",
            "phase": "policy_design_substrate_residual_verification",
            "message": issue.message,
            "evidence_ref": "quality_evidence/policy_design_case.json",
            "next_action": SUBSTRATE_RESIDUAL_VERIFICATION_NEXT_ACTION,
            "missing_input": issue.field,
            "pdd_id": issue.family_id
            if issue.family_id.startswith("PDD-")
            else None,
            "blocking": True,
        }
        for issue in issues
    ]


def dump_policy_design_case_record_registry_report_json(
    payload: Mapping[str, Any],
) -> str:
    """Serialize a record-registry report for CLI or evidence output."""

    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _case_record_family_rows(value: object) -> tuple[dict[str, Any], ...]:
    if isinstance(value, Mapping):
        rows: list[dict[str, Any]] = []
        for family_id, row in value.items():
            if isinstance(row, Mapping):
                normalized = dict(row)
                normalized.setdefault("family_id", str(family_id))
                rows.append(normalized)
        return tuple(rows)
    if isinstance(value, list | tuple):
        return tuple(dict(row) for row in value if isinstance(row, Mapping))
    return ()


def _case_record_rows(value: object) -> tuple[dict[str, Any], ...]:
    if isinstance(value, Mapping):
        rows: list[dict[str, Any]] = []
        for record_id, row in value.items():
            if isinstance(row, Mapping):
                normalized = dict(row)
                normalized.setdefault("record_id", str(record_id))
                rows.append(normalized)
        return tuple(rows)
    if isinstance(value, list | tuple):
        return tuple(dict(row) for row in value if isinstance(row, Mapping))
    return ()


def _case_record_family_coverage_issues(
    row: Mapping[str, Any],
    records: list[dict[str, Any]],
    *,
    index: int,
) -> list[PolicyDesignCaseRecordRegistryIssue]:
    family_id = _case_family_row_id(row, index)
    issues: list[PolicyDesignCaseRecordRegistryIssue] = []
    status = _status(row.get("status") or "present")
    required_text_fields = (
        "schema_owner",
        "producer_owner",
        "reader_owner",
        "schema_name",
        "scorecard_gate",
    )
    for field in required_text_fields:
        if not _non_empty_string(row.get(field)):
            issues.append(
                _coverage_issue(
                    f"policy_design_case_record_family_{field}_missing",
                    family_id,
                    field,
                    f"Runtime record family `{family_id}` is missing `{field}`.",
                    value=row.get(field),
                )
            )
    if not _non_empty_string(row.get("readiness_gate")):
        issues.append(
            _coverage_issue(
                "policy_design_case_record_family_readiness_gate_missing",
                family_id,
                "readiness_gate",
                f"Runtime record family `{family_id}` is missing readiness_gate.",
                value=row.get("readiness_gate"),
            )
        )
    for owner_field in ("schema_owner", "producer_owner", "reader_owner"):
        if _non_empty_string(row.get(owner_field)) and not _team_owner(row.get(owner_field)):
            issues.append(
                _coverage_issue(
                    f"policy_design_case_record_family_{owner_field}_invalid",
                    family_id,
                    owner_field,
                    f"Runtime record family `{family_id}` must name a team owner.",
                    value=row.get(owner_field),
                )
            )

    if status not in (
        POLICY_DESIGN_CASE_RECORD_FAMILY_PRESENT_STATUSES
        | POLICY_DESIGN_CASE_RECORD_FAMILY_POLICY_STATUSES
    ):
        issues.append(
            _coverage_issue(
                "policy_design_case_record_family_status_invalid",
                family_id,
                "status",
                "Runtime record family status must be present, blocked, or out_of_scope.",
                value=row.get("status"),
            )
        )
    if status in POLICY_DESIGN_CASE_RECORD_FAMILY_POLICY_STATUSES:
        issues.extend(_typed_authority_policy_issues(row, family_id=family_id))
    elif not records:
        issues.append(
            _coverage_issue(
                "policy_design_case_record_family_runtime_record_missing",
                family_id,
                "records",
                (
                    "A present Policy Design Case record family must have at least "
                    "one concrete runtime record."
                ),
            )
        )
    return issues


def _case_runtime_record_issues(
    row: Mapping[str, Any],
    *,
    index: int,
) -> list[PolicyDesignCaseRecordRegistryIssue]:
    record_id = _text_field(row.get("record_id")) or f"records[{index}]"
    family_id = _case_record_family_id(row, index)
    issues: list[PolicyDesignCaseRecordRegistryIssue] = []
    if not _non_empty_string(row.get("record_id")):
        issues.append(
            _coverage_issue(
                "policy_design_case_runtime_record_id_missing",
                family_id,
                "records.record_id",
                "Every Policy Design Case runtime record must have a record_id.",
            )
        )
    if not _non_empty_string(family_id):
        issues.append(
            _coverage_issue(
                "policy_design_case_runtime_record_family_missing",
                record_id,
                "records.family_id",
                "Every Policy Design Case runtime record must bind to a family_id.",
            )
        )
    for field in ("producer_owner", "reader_owner"):
        if not _team_owner(row.get(field)):
            issues.append(
                _coverage_issue(
                    f"policy_design_case_runtime_record_{field}_missing",
                    family_id,
                    f"records.{record_id}.{field}",
                    "Runtime records must name producer and reader team owners.",
                    value=row.get(field),
                )
            )
    if not (
        _non_empty_string(row.get("schema_name"))
        or _non_empty_string(row.get("schema_version"))
    ):
        issues.append(
            _coverage_issue(
                "policy_design_case_runtime_record_schema_missing",
                family_id,
                f"records.{record_id}.schema_name",
                "Runtime records must identify their schema.",
            )
        )
    if not _non_empty_string(row.get("readiness_gate") or row.get("readiness_check")):
        issues.append(
            _coverage_issue(
                "policy_design_case_runtime_record_readiness_gate_missing",
                family_id,
                f"records.{record_id}.readiness_gate",
                "Runtime records must identify the readiness gate that reads them.",
            )
        )
    if not _coverage_runtime_artifact_ref(
        row.get("evidence_ref") or row.get("cas_ref") or row.get("record_ref")
    ):
        issues.append(
            _coverage_issue(
                "policy_design_case_runtime_record_ref_missing",
                family_id,
                f"records.{record_id}.evidence_ref",
                "Runtime records must carry a CAS, artifact, or runtime evidence ref.",
                value=row.get("evidence_ref") or row.get("cas_ref") or row.get("record_ref"),
            )
        )
    if not _coverage_runtime_event_ref(row.get("runtime_event_ref")):
        issues.append(
            _coverage_issue(
                "policy_design_case_runtime_record_event_missing",
                family_id,
                f"records.{record_id}.runtime_event_ref",
                "Runtime records must carry a runtime event ref.",
                value=row.get("runtime_event_ref"),
            )
        )
    envelope = row.get("authority_envelope") or row.get("runtime_authority_envelope")
    if not isinstance(envelope, Mapping):
        issues.append(
            _coverage_issue(
                "policy_design_case_runtime_record_authority_envelope_missing",
                family_id,
                f"records.{record_id}.authority_envelope",
                "Runtime records must include a producer authority envelope.",
            )
        )
    else:
        issues.extend(
            _runtime_record_authority_envelope_issues(
                envelope,
                family_id=family_id,
                field=f"records.{record_id}.authority_envelope",
            )
        )
    return issues


def _runtime_record_authority_envelope_issues(
    envelope: Mapping[str, Any],
    *,
    family_id: str,
    field: str,
) -> list[PolicyDesignCaseRecordRegistryIssue]:
    issues: list[PolicyDesignCaseRecordRegistryIssue] = []
    provenance_kind = _status(envelope.get("provenance_kind"))
    if provenance_kind not in {"runtime_emitted", "runtime_derived", "runtime_blocker"}:
        issues.append(
            _coverage_issue(
                "policy_design_case_runtime_record_authority_provenance_invalid",
                family_id,
                f"{field}.provenance_kind",
                "Runtime record authority envelopes must be runtime-owned.",
                value=envelope.get("provenance_kind"),
            )
        )
    authority_role = _status(envelope.get("authority_role") or envelope.get("role"))
    if authority_role not in {
        "producer_authority",
        "reader_authority",
        "runtime_quality_authority",
    }:
        issues.append(
            _coverage_issue(
                "policy_design_case_runtime_record_authority_role_invalid",
                family_id,
                f"{field}.authority_role",
                "Runtime record authority envelopes must name an authority role.",
                value=envelope.get("authority_role") or envelope.get("role"),
            )
        )
    if not _coverage_runtime_artifact_ref(envelope.get("cas_ref") or envelope.get("evidence_ref")):
        issues.append(
            _coverage_issue(
                "policy_design_case_runtime_record_authority_ref_missing",
                family_id,
                f"{field}.cas_ref",
                "Runtime record authority envelopes must include CAS evidence.",
                value=envelope.get("cas_ref") or envelope.get("evidence_ref"),
            )
        )
    if not _coverage_runtime_event_ref(envelope.get("runtime_event_ref")):
        issues.append(
            _coverage_issue(
                "policy_design_case_runtime_record_authority_event_missing",
                family_id,
                f"{field}.runtime_event_ref",
                "Runtime record authority envelopes must include a runtime event.",
                value=envelope.get("runtime_event_ref"),
            )
        )
    return issues


def _typed_authority_policy_issues(
    row: Mapping[str, Any],
    *,
    family_id: str,
) -> list[PolicyDesignCaseRecordRegistryIssue]:
    policy = row.get("typed_authority_policy") or row.get("authority_policy")
    if not isinstance(policy, Mapping):
        return [
            _coverage_issue(
                "policy_design_case_record_family_typed_authority_policy_missing",
                family_id,
                "typed_authority_policy",
                (
                    "Blocked or out-of-scope record families must cite a typed "
                    "authority policy."
                ),
            )
        ]
    issues: list[PolicyDesignCaseRecordRegistryIssue] = []
    if not _non_empty_string(policy.get("policy_code") or policy.get("code")):
        issues.append(
            _coverage_issue(
                "policy_design_case_record_family_typed_authority_policy_code_missing",
                family_id,
                "typed_authority_policy.policy_code",
                "Typed authority policy must name its policy code.",
            )
        )
    if _status(policy.get("status")) not in POLICY_DESIGN_CASE_RECORD_FAMILY_POLICY_STATUSES:
        issues.append(
            _coverage_issue(
                "policy_design_case_record_family_typed_authority_policy_status_invalid",
                family_id,
                "typed_authority_policy.status",
                "Typed authority policy status must be blocked or out_of_scope.",
                value=policy.get("status"),
            )
        )
    if not _coverage_runtime_artifact_ref(policy.get("evidence_ref") or policy.get("cas_ref")):
        issues.append(
            _coverage_issue(
                "policy_design_case_record_family_typed_authority_policy_ref_missing",
                family_id,
                "typed_authority_policy.evidence_ref",
                "Typed authority policy must include runtime evidence.",
                value=policy.get("evidence_ref") or policy.get("cas_ref"),
            )
        )
    if not _coverage_runtime_event_ref(policy.get("runtime_event_ref")):
        issues.append(
            _coverage_issue(
                "policy_design_case_record_family_typed_authority_policy_event_missing",
                family_id,
                "typed_authority_policy.runtime_event_ref",
                "Typed authority policy must include a runtime event.",
                value=policy.get("runtime_event_ref"),
            )
        )
    return issues


def _case_family_authority_status(
    family: Mapping[str, Any],
    records: list[dict[str, Any]],
) -> str:
    status = _status(family.get("status") or "present")
    if status in POLICY_DESIGN_CASE_RECORD_FAMILY_POLICY_STATUSES:
        return "typed_authority_policy"
    for record in records:
        envelope = record.get("authority_envelope") or record.get("runtime_authority_envelope")
        if isinstance(envelope, Mapping) and _status(envelope.get("provenance_kind")) in {
            "runtime_emitted",
            "runtime_derived",
            "runtime_blocker",
        }:
            return "runtime_authority_present"
    return "runtime_authority_missing"


def _case_family_row_id(row: Mapping[str, Any], index: int) -> str:
    value = row.get("family_id") or row.get("record_family")
    if _non_empty_string(value):
        return str(value).strip()
    return f"record_families[{index}]"


def _case_record_family_id(row: Mapping[str, Any], index: int) -> str:
    value = row.get("family_id") or row.get("record_family")
    if _non_empty_string(value):
        return str(value).strip()
    return f"records[{index}]"


def _coverage_issue(
    code: str,
    family_id: str,
    field: str,
    message: str,
    *,
    value: object | None = None,
) -> PolicyDesignCaseRecordRegistryIssue:
    return PolicyDesignCaseRecordRegistryIssue(
        code=code,
        family_id=family_id,
        field=field,
        message=message,
        value=value,
    )


def _text_field(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _coverage_runtime_artifact_ref(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or len(text) > 512 or any(char in text for char in "\r\n\t"):
        return False
    return text.startswith(("sha256:", "cas://", "artifact://"))


def _coverage_runtime_event_ref(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or len(text) > 512 or any(char in text for char in "\r\n\t"):
        return False
    return text.startswith(("event://", "sha256:", "cas://"))


def _record_family_row_issues(
    row: Mapping[str, Any],
    *,
    index: int,
    known_readiness_checks: frozenset[str] | set[str],
    known_enforcement_functions: frozenset[str] | set[str],
) -> list[PolicyDesignCaseRecordRegistryIssue]:
    family_id = _row_family_id(row, index)
    issues: list[PolicyDesignCaseRecordRegistryIssue] = []

    required_text_fields = {
        "family_id",
        "title",
        "producer_owner",
        "reader_owner",
        "schema_name",
        "scorecard_gate",
        "readiness_check",
        "enforcement_function",
        "next_diagnostic_command",
        "maturity_floor",
    }
    for field in sorted(required_text_fields):
        if field not in row:
            issues.append(_missing_field_issue(family_id, field))
            continue
        if not _non_empty_string(row.get(field)):
            issues.append(_invalid_text_issue(family_id, field, row.get(field)))

    for owner_field in ("producer_owner", "reader_owner"):
        if owner_field in row and not _team_owner(row.get(owner_field)):
            issues.append(
                PolicyDesignCaseRecordRegistryIssue(
                    code="policy_design_case_record_family_owner_missing",
                    family_id=family_id,
                    field=owner_field,
                    message=(
                        f"Every Policy Design Case family must name a team owner for {owner_field}."
                    ),
                    value=row.get(owner_field),
                )
            )

    applicability = row.get("applicability")
    allowed_applicability = {item.value for item in PolicyDesignCaseRecordApplicability}
    if not isinstance(applicability, str) or applicability not in allowed_applicability:
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_record_family_applicability_invalid",
                family_id=family_id,
                field="applicability",
                message="Applicability must be required, profile_scoped, or not_applicable.",
                value=applicability,
            )
        )

    evidence = row.get("applicability_evidence")
    if not isinstance(evidence, Mapping):
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_record_family_evidence_missing",
                family_id=family_id,
                field="applicability_evidence",
                message="Applicability must be backed by typed evidence.",
                value=evidence,
            )
        )
    else:
        issues.extend(_applicability_evidence_issues(family_id, evidence))

    readiness_check = row.get("readiness_check")
    if _non_empty_string(readiness_check) and str(readiness_check).strip() not in (
        known_readiness_checks
    ):
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_record_family_readiness_check_unknown",
                family_id=family_id,
                field="readiness_check",
                message="Readiness check must map to a known readiness enforcer.",
                value=readiness_check,
            )
        )

    enforcement_function = row.get("enforcement_function")
    if not _non_empty_string(enforcement_function):
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_record_family_enforcement_function_missing",
                family_id=family_id,
                field="enforcement_function",
                message="Every family must name the enforcement function that reads it.",
                value=enforcement_function,
            )
        )
    elif str(enforcement_function).strip() not in known_enforcement_functions:
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_record_family_enforcement_function_unknown",
                family_id=family_id,
                field="enforcement_function",
                message="Enforcement function must map to a known runtime-quality reader.",
                value=enforcement_function,
            )
        )

    sdd_facets = row.get("sdd_facets")
    if not isinstance(sdd_facets, list) or not _string_list(sdd_facets):
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_record_family_sdd_facets_missing",
                family_id=family_id,
                field="sdd_facets",
                message="Every family row must list the SDD facets it covers.",
                value=sdd_facets,
            )
        )

    return issues


def _substrate_residual_binding_issues(
    binding: Mapping[str, Any],
    *,
    index: int,
    record_families: Mapping[str, Mapping[str, Any]],
) -> list[PolicyDesignCaseRecordRegistryIssue]:
    diagnostic_id = _binding_diagnostic_id(binding, index)
    issues: list[PolicyDesignCaseRecordRegistryIssue] = []
    required_text_fields = {
        "binding_id",
        "diagnostic_id",
        "title",
        "record_family_id",
        "scorecard_gate",
        "readiness_check",
        "enforcement_function",
        "next_diagnostic_command",
        "owner",
    }
    for field in sorted(required_text_fields):
        if field not in binding:
            issues.append(_substrate_binding_issue(diagnostic_id, field, "missing"))
            continue
        if not _non_empty_string(binding.get(field)):
            issues.append(_substrate_binding_issue(diagnostic_id, field, "invalid"))

    owner = binding.get("owner")
    if _non_empty_string(owner) and not _team_owner(owner):
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_substrate_residual_binding_owner_missing",
                family_id=diagnostic_id,
                field="owner",
                message="Substrate-residual binding owner must be a team owner.",
                value=owner,
            )
        )

    record_family_id = str(binding.get("record_family_id") or "").strip()
    family_row = record_families.get(record_family_id)
    if not family_row:
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_substrate_residual_record_family_unknown",
                family_id=diagnostic_id,
                field="record_family_id",
                message="Substrate-residual binding must target a known PDC family.",
                value=record_family_id,
            )
        )
    record_facets = _string_list(binding.get("record_facets"))
    if not record_facets:
        issues.append(_substrate_binding_issue(diagnostic_id, "record_facets", "missing"))
    elif family_row:
        allowed_facets = set(_string_list(family_row.get("sdd_facets")))
        for facet in record_facets:
            if facet not in allowed_facets:
                issues.append(
                    PolicyDesignCaseRecordRegistryIssue(
                        code=("policy_design_case_substrate_residual_record_facet_unknown"),
                        family_id=diagnostic_id,
                        field="record_facets",
                        message=(
                            "Substrate-residual binding facet must be declared on "
                            "the target record family."
                        ),
                        value=facet,
                    )
                )

    for field in ("runtime_records", "test_paths"):
        values = _string_list(binding.get(field))
        if not values:
            issues.append(_substrate_binding_issue(diagnostic_id, field, "missing"))
        for value in values:
            if field == "test_paths" and not value.endswith(".py"):
                issues.append(
                    PolicyDesignCaseRecordRegistryIssue(
                        code="policy_design_case_substrate_residual_test_path_invalid",
                        family_id=diagnostic_id,
                        field=field,
                        message="Substrate-residual test paths must point at Python tests.",
                        value=value,
                    )
                )

    if binding.get("readiness_check") != SUBSTRATE_RESIDUAL_BINDINGS_READINESS_CHECK:
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_substrate_residual_readiness_check_unknown",
                family_id=diagnostic_id,
                field="readiness_check",
                message="Substrate-residual bindings must use the Phase 28.2 check.",
                value=binding.get("readiness_check"),
            )
        )
    if binding.get("enforcement_function") != (SUBSTRATE_RESIDUAL_BINDINGS_ENFORCEMENT_FUNCTION):
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_substrate_residual_enforcement_unknown",
                family_id=diagnostic_id,
                field="enforcement_function",
                message="Substrate-residual binding must name its runtime validator.",
                value=binding.get("enforcement_function"),
            )
        )

    return issues


def _substrate_binding_issue(
    diagnostic_id: str,
    field: str,
    kind: str,
) -> PolicyDesignCaseRecordRegistryIssue:
    code = f"policy_design_case_substrate_residual_binding_{kind}"
    return PolicyDesignCaseRecordRegistryIssue(
        code=code,
        family_id=diagnostic_id,
        field=field,
        message=f"Substrate-residual binding field `{field}` is {kind}.",
    )


def _substrate_verification_binding_issues(
    row: Mapping[str, Any],
    *,
    expected: PolicyDesignCaseSubstrateResidualBinding,
) -> list[PolicyDesignCaseRecordRegistryIssue]:
    diagnostic_id = expected.diagnostic_id
    issues: list[PolicyDesignCaseRecordRegistryIssue] = []
    required_text_fields = ("diagnostic_id", "record_family_id", "owner", "status")
    for field in required_text_fields:
        value = row.get(field)
        if field == "diagnostic_id":
            value = row.get("diagnostic_id") or row.get("pdd_id")
        if not _non_empty_string(value):
            issues.append(
                _substrate_verification_issue(
                    "policy_design_substrate_residual_verification_binding_incomplete",
                    f"pdd_bindings.{diagnostic_id}.{field}",
                    (
                        "Every substrate-residual PDD binding must include identity, "
                        "owner, and status."
                    ),
                    family_id=diagnostic_id,
                )
            )
    if str(row.get("record_family_id") or "").strip() != expected.record_family_id:
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_family_mismatch",
                f"pdd_bindings.{diagnostic_id}.record_family_id",
                "Substrate-residual PDD binding must target the registry record family.",
                family_id=diagnostic_id,
                value=row.get("record_family_id"),
            )
        )
    owner = row.get("owner")
    if _non_empty_string(owner) and not _team_owner(owner):
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_owner_invalid",
                f"pdd_bindings.{diagnostic_id}.owner",
                "Substrate-residual PDD binding owner must be a team owner.",
                family_id=diagnostic_id,
                value=owner,
            )
        )
    status = _status(row.get("status"))
    if status not in SUBSTRATE_RESIDUAL_PASSING_STATUSES:
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_binding_not_pass",
                f"pdd_bindings.{diagnostic_id}.status",
                "Substrate-residual PDD binding must be passing for serious closeout.",
                family_id=diagnostic_id,
                value=row.get("status"),
            )
        )
    facets = set(_string_list(row.get("record_facets") or row.get("facets")))
    expected_facets = set(expected.record_facets)
    if not facets >= expected_facets:
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_facets_missing",
                f"pdd_bindings.{diagnostic_id}.record_facets",
                "Substrate-residual PDD binding is missing required record facets.",
                family_id=diagnostic_id,
                value=sorted(expected_facets - facets),
            )
        )
    record_refs = _string_list(row.get("record_refs") or row.get("runtime_record_refs"))
    if not record_refs:
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_record_refs_missing",
                f"pdd_bindings.{diagnostic_id}.record_refs",
                "Substrate-residual PDD binding must point at runtime record refs.",
                family_id=diagnostic_id,
            )
        )
    if not _runtime_artifact_ref(row.get("evidence_ref") or row.get("cas_ref")):
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_runtime_ref_missing",
                f"pdd_bindings.{diagnostic_id}.evidence_ref",
                "Substrate-residual PDD binding must include runtime evidence.",
                family_id=diagnostic_id,
                value=row.get("evidence_ref"),
            )
        )
    if not _runtime_event_ref(row.get("runtime_event_ref")):
        issues.append(
            _substrate_verification_issue(
                "policy_design_substrate_residual_verification_runtime_event_missing",
                f"pdd_bindings.{diagnostic_id}.runtime_event_ref",
                "Substrate-residual PDD binding must include a runtime event.",
                family_id=diagnostic_id,
                value=row.get("runtime_event_ref"),
            )
        )
    return issues


def _substrate_verification_issue(
    code: str,
    field: str,
    message: str,
    *,
    family_id: str = SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_KEY,
    value: object | None = None,
) -> PolicyDesignCaseRecordRegistryIssue:
    return PolicyDesignCaseRecordRegistryIssue(
        code=code,
        family_id=family_id,
        field=field,
        message=message,
        value=value,
    )


def _applicability_evidence_issues(
    family_id: str,
    evidence: Mapping[str, Any],
) -> list[PolicyDesignCaseRecordRegistryIssue]:
    issues: list[PolicyDesignCaseRecordRegistryIssue] = []
    allowed_kinds = {item.value for item in PolicyDesignCaseApplicabilityEvidenceKind}
    kind = evidence.get("kind")
    if not isinstance(kind, str) or kind not in allowed_kinds:
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_record_family_evidence_kind_invalid",
                family_id=family_id,
                field="applicability_evidence.kind",
                message="Applicability evidence kind must be a known typed evidence kind.",
                value=kind,
            )
        )
    for field in ("source", "reason"):
        if not _non_empty_string(evidence.get(field)):
            issues.append(
                PolicyDesignCaseRecordRegistryIssue(
                    code="policy_design_case_record_family_evidence_missing",
                    family_id=family_id,
                    field=f"applicability_evidence.{field}",
                    message="Applicability evidence must name its source and reason.",
                    value=evidence.get(field),
                )
            )
    profiles = evidence.get("profiles")
    if not isinstance(profiles, list) or not _string_list(profiles):
        issues.append(
            PolicyDesignCaseRecordRegistryIssue(
                code="policy_design_case_record_family_evidence_missing",
                family_id=family_id,
                field="applicability_evidence.profiles",
                message="Applicability evidence must list covered authority profiles.",
                value=profiles,
            )
        )
    return issues


def _missing_field_issue(
    family_id: str,
    field: str,
) -> PolicyDesignCaseRecordRegistryIssue:
    if field in {"producer_owner", "reader_owner"}:
        code = "policy_design_case_record_family_owner_missing"
    elif field == "enforcement_function":
        code = "policy_design_case_record_family_enforcement_function_missing"
    else:
        code = "policy_design_case_record_family_field_missing"
    return PolicyDesignCaseRecordRegistryIssue(
        code=code,
        family_id=family_id,
        field=field,
        message=f"Required Policy Design Case registry field `{field}` is missing.",
    )


def _invalid_text_issue(
    family_id: str,
    field: str,
    value: object,
) -> PolicyDesignCaseRecordRegistryIssue:
    if field in {"producer_owner", "reader_owner"}:
        code = "policy_design_case_record_family_owner_missing"
    elif field == "enforcement_function":
        code = "policy_design_case_record_family_enforcement_function_missing"
    else:
        code = "policy_design_case_record_family_field_invalid"
    return PolicyDesignCaseRecordRegistryIssue(
        code=code,
        family_id=family_id,
        field=field,
        message=f"Policy Design Case registry field `{field}` must be non-empty text.",
        value=value,
    )


def _row_family_id(row: Mapping[str, Any], index: int) -> str:
    value = row.get("family_id")
    if _non_empty_string(value):
        return str(value).strip()
    return f"record_families[{index}]"


def _binding_diagnostic_id(binding: Mapping[str, Any], index: int) -> str:
    value = binding.get("diagnostic_id")
    if _non_empty_string(value):
        return str(value).strip()
    return f"substrate_residual_bindings[{index}]"


def _record_family_index(source: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = source.get("record_families")
    if not isinstance(rows, list):
        rows = [row.as_dict() for row in DEFAULT_POLICY_DESIGN_CASE_RECORD_REGISTRY]
    index: dict[str, Mapping[str, Any]] = {}
    for raw_row in rows:
        if not isinstance(raw_row, Mapping):
            continue
        family_id = raw_row.get("family_id")
        if _non_empty_string(family_id):
            index[str(family_id).strip()] = raw_row
    return index


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _team_owner(value: object) -> bool:
    return _non_empty_string(value) and str(value).strip().startswith("team-")


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _mapping_rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _status(value: object) -> str:
    return str(value or "").strip().casefold().replace("-", "_")


def _runtime_artifact_ref(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return text.startswith(("sha256:", "cas://"))


def _runtime_event_ref(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return text.startswith(("event://", "sha256:", "cas://"))


def _evidence(
    *,
    kind: PolicyDesignCaseApplicabilityEvidenceKind,
    reason: str,
    profiles: tuple[str, ...] = ("research", "governed", "production"),
) -> PolicyDesignCaseApplicabilityEvidence:
    return PolicyDesignCaseApplicabilityEvidence(
        kind=kind,
        source=(
            "docs/system-design-decisions/"
            "policy-design-best-in-class-operating-model.md#minimum-policy-design-case-record-families"
        ),
        reason=reason,
        profiles=profiles,
    )


def _family(
    family_id: str,
    *,
    title: str,
    producer_owner: str,
    facets: tuple[str, ...],
    applicability: PolicyDesignCaseRecordApplicability = (
        PolicyDesignCaseRecordApplicability.REQUIRED
    ),
    evidence_kind: PolicyDesignCaseApplicabilityEvidenceKind = (
        PolicyDesignCaseApplicabilityEvidenceKind.SDD_MINIMUM_RECORD_FAMILY
    ),
    evidence_reason: str = ("The SDD names this as a minimum Policy Design Case record family."),
    profiles: tuple[str, ...] = ("research", "governed", "production"),
    reader_owner: str = "team-quality-closeout",
    maturity_floor: str = "stub_or_typed_blocker",
) -> PolicyDesignCaseRecordFamily:
    short_name = family_id.removesuffix(".v1")
    return PolicyDesignCaseRecordFamily(
        family_id=family_id,
        title=title,
        applicability=applicability,
        applicability_evidence=_evidence(
            kind=evidence_kind,
            reason=evidence_reason,
            profiles=profiles,
        ),
        producer_owner=producer_owner,
        reader_owner=reader_owner,
        schema_name=f"policyos.policy_design_case.{family_id}",
        scorecard_gate=f"policy_design_case.{short_name}.present_or_blocked",
        readiness_check=RECORD_REGISTRY_READINESS_CHECK,
        enforcement_function=RECORD_REGISTRY_ENFORCEMENT_FUNCTION,
        next_diagnostic_command=DEFAULT_NEXT_DIAGNOSTIC_COMMAND,
        maturity_floor=maturity_floor,
        sdd_facets=facets,
    )


def _substrate_binding(
    diagnostic_id: str,
    *,
    title: str,
    record_family_id: str,
    facets: tuple[str, ...],
    runtime_records: tuple[str, ...],
    test_paths: tuple[str, ...],
    owner: str = "team-runtime-quality",
) -> PolicyDesignCaseSubstrateResidualBinding:
    short_id = diagnostic_id.casefold().replace("-", "_")
    return PolicyDesignCaseSubstrateResidualBinding(
        binding_id=f"substrate_residual.{short_id}",
        diagnostic_id=diagnostic_id,
        title=title,
        record_family_id=record_family_id,
        record_facets=facets,
        runtime_records=runtime_records,
        scorecard_gate=SUBSTRATE_RESIDUAL_BINDINGS_SCORECARD_GATE,
        readiness_check=SUBSTRATE_RESIDUAL_BINDINGS_READINESS_CHECK,
        enforcement_function=SUBSTRATE_RESIDUAL_BINDINGS_ENFORCEMENT_FUNCTION,
        test_paths=test_paths,
        next_diagnostic_command=SUBSTRATE_RESIDUAL_BINDINGS_NEXT_DIAGNOSTIC_COMMAND,
        owner=owner,
    )


DEFAULT_POLICY_DESIGN_CASE_RECORD_REGISTRY = (
    _family(
        "intent_authoring_and_capture_risk.v1",
        title="Intent authoring and requester-capture risk",
        producer_owner="team-runtime-control",
        facets=(
            "intent_envelope",
            "authoring_provenance",
            "requester_preference",
            "requester_capture_risk",
            "challenge_depth",
        ),
    ),
    _family(
        "capability_mode_and_fallback_selection.v1",
        title="Capability mode and fallback selection",
        producer_owner="team-runtime-control",
        facets=(
            "capability_ledger",
            "dormant_capability_inventory",
            "mode_ledger",
            "fallback_degradation_ledger",
            "skipped_duty_blockers",
            "skip_causality_ledger",
            "effective_configuration_ledger",
            "environment_provenance",
        ),
    ),
    _family(
        "concept_and_jurisdiction_spine.v1",
        title="Concept and jurisdiction spine",
        producer_owner="team-policy-semantics",
        facets=(
            "concept_spine",
            "ontology_reconciliation",
            "multi_jurisdiction_hierarchy",
            "conflict_preemption_rules",
        ),
    ),
    _family(
        "legal_authority_and_competence.v1",
        title="Legal authority and competence",
        producer_owner="team-domain-producers",
        facets=(
            "legal_retrieval_report",
            "normative_applicability",
            "institutional_competence",
            "legal_blockers",
        ),
    ),
    _family(
        "data_source_semantic_lineage.v1",
        title="Data source semantic lineage",
        producer_owner="team-domain-producers",
        facets=(
            "source_selection",
            "data_forge_snapshot_binding",
            "dataset_binding",
            "schema_dictionary",
            "field_transform_lineage",
            "source_rights",
        ),
    ),
    _family(
        "scholar_academic_evidence.v1",
        title="Scholar academic and grey-literature evidence",
        producer_owner="team-domain-producers",
        facets=(
            "research_intent",
            "scholar_query_graph",
            "provider_traces",
            "source_scoring",
            "citations",
            "freshness",
            "support_conflict_links",
            "literature_independence",
        ),
    ),
    _family(
        "numeric_time_and_geography_semantics.v1",
        title="Numeric, time, and geography semantics",
        producer_owner="team-policy-semantics",
        facets=(
            "unit",
            "currency",
            "price_base",
            "exchange",
            "inflation",
            "calendar",
            "geography",
            "freshness",
            "policy_time_semantics",
            "retention",
        ),
    ),
    _family(
        "method_selection_and_validity.v1",
        title="Method selection and validity",
        producer_owner="team-science-quality",
        facets=(
            "candidate_methods",
            "selected_rejected_methods",
            "assumptions",
            "uncertainty",
            "sensitivity",
            "identification",
            "transportability",
            "falsification",
            "validity_limits",
            "simulation_boundary_ledger",
            "evidence_mode_ledger",
            "counterfactual_lineage",
        ),
    ),
    _family(
        "evidence_portfolio_and_synthesis.v1",
        title="Evidence portfolio and synthesis",
        producer_owner="team-science-quality",
        facets=(
            "portfolio_design",
            "predeclared_claim_strands",
            "candidate_data_source_families",
            "candidate_method_families",
            "defensible_specification_space",
            "inclusion_exclusion_rules",
            "independence_map",
            "method_equivalence_collapse",
            "effective_independent_count",
            "multiverse_specification_curve",
            "disconfirming_ledger",
            "convergence_report",
            "synthesis_report",
            "certainty_rating",
            "stopping_rule",
            "cost_proportionality",
        ),
    ),
    _family(
        "structured_judgement_and_consultation.v1",
        title="Structured judgement and consultation",
        producer_owner="team-quality-closeout",
        applicability=PolicyDesignCaseRecordApplicability.PROFILE_SCOPED,
        evidence_kind=PolicyDesignCaseApplicabilityEvidenceKind.AUTHORITY_PROFILE_SCOPE,
        evidence_reason=(
            "Structured judgement and consultation are mandatory when an authority "
            "profile, policy domain, or publication workflow places them in scope."
        ),
        profiles=("governed", "production"),
        facets=(
            "expert_elicitation",
            "judgement_provenance",
            "stakeholder_map",
            "consultation_evidence",
            "response_to_comment",
        ),
    ),
    _family(
        "options_objectives_and_tradeoffs.v1",
        title="Options, objectives, and tradeoffs",
        producer_owner="team-science-quality",
        facets=(
            "baseline_no_action_option",
            "candidate_options",
            "rejected_options",
            "objective_function",
            "tradeoff_weights",
            "social_weights",
            "welfare_bounds",
            "distributional_effects",
            "qualitative_effects",
            "risk",
            "uncertainty",
            "foundry_welfare_uncertainty_refs",
            "ir_distributional_fairness_mobility_welfare_refs",
            "proportionality",
        ),
    ),
    _family(
        "claim_argument_evidence_case.v1",
        title="Claim argument and evidence case",
        producer_owner="team-claim-compiler",
        facets=(
            "sacm_cae_gsn_profile",
            "runtime_assurance_case_profile",
            "claims",
            "arguments",
            "warrants",
            "assumptions",
            "applicability_limits",
            "explanation_reliability",
            "evidence_refs",
            "rebuttals",
            "counter_evidence",
            "deficits",
            "requester_capture_challenge",
            "blockers",
            "sacm_cae_gsn_export",
            "triangulation",
        ),
    ),
    _family(
        "implementation_monitoring_and_evaluation.v1",
        title="Implementation monitoring and evaluation",
        producer_owner="team-ddm",
        applicability=PolicyDesignCaseRecordApplicability.PROFILE_SCOPED,
        evidence_kind=PolicyDesignCaseApplicabilityEvidenceKind.AUTHORITY_PROFILE_SCOPE,
        evidence_reason=(
            "Implementation, monitoring, and evaluation records are required for "
            "governed or production decisions and for research runs that publish a "
            "policy recommendation."
        ),
        profiles=("governed", "production"),
        facets=(
            "implementation_contract",
            "monitoring_plan",
            "evaluation_design",
            "pre_publication_challenge",
            "ddm_post_market_evidence",
            "ddm_shift_events",
            "ddm_degradation_events",
            "ddm_readiness_events",
            "ddm_incident_events",
            "ddm_root_cause_events",
            "post_market_monitoring",
            "resilience_matrix",
            "observed_vs_modeled_resilience",
        ),
    ),
    _family(
        "human_oversight_independence_and_review.v1",
        title="Human oversight, independence, and review",
        producer_owner="team-quality-closeout",
        facets=(
            "producer_independence",
            "reviewer_independence",
            "review_effectiveness",
            "dissent",
            "override",
            "rubber_stamp_risk",
        ),
    ),
    _family(
        "integrity_self_fmea_and_maturity.v1",
        title="Integrity self-FMEA and maturity",
        producer_owner="team-quality-closeout",
        facets=(
            "evidence_graph_threat_model",
            "prompt_injection_threat",
            "poisoned_dataset_threat",
            "stale_index_threat",
            "malicious_tenant_threat",
            "forged_provenance_threat",
            "compromised_plugin_threat",
            "local_client_leakage_threat",
            "insider_mutation_threat",
            "non_adversarial_self_fmea",
            "schema_migration_errors",
            "partial_case_graphs",
            "contradictory_records",
            "stale_generated_surfaces",
            "operator_workarounds",
            "box_ticking_failure",
            "record_family_maturity",
            "partial_case_contradictions",
            "partial_state_consistency",
            "retry_reconciliation",
        ),
    ),
    _family(
        "lifecycle_ex_post_and_calibration.v1",
        title="Lifecycle, ex-post outcomes, and calibration",
        producer_owner="team-science-quality",
        applicability=PolicyDesignCaseRecordApplicability.PROFILE_SCOPED,
        evidence_kind=PolicyDesignCaseApplicabilityEvidenceKind.AUTHORITY_PROFILE_SCOPE,
        evidence_reason=(
            "Lifecycle and ex-post calibration evidence becomes mandatory for "
            "published, superseded, recalled, or reassessed policy decisions."
        ),
        profiles=("governed", "production"),
        facets=(
            "case_lifecycle",
            "continuous_governance_reissue",
            "supersession",
            "continuous_governance_withdrawal",
            "validity_reports",
            "recall_retraction",
            "ex_post_outcomes",
            "reassessment",
            "calibration_track_record",
            "backtesting",
            "calibration_leaderboard",
            "memory_contamination_checks",
            "claim_prediction_outcome_links",
            "future_method_uncertainty_priors",
        ),
    ),
    _family(
        "publication_trust_and_external_governance.v1",
        title="Publication trust and external governance",
        producer_owner="team-core-audit",
        applicability=PolicyDesignCaseRecordApplicability.PROFILE_SCOPED,
        evidence_kind=PolicyDesignCaseApplicabilityEvidenceKind.AUTHORITY_PROFILE_SCOPE,
        evidence_reason=(
            "Publication trust and external-governance records are mandatory when "
            "a case is approved, signed, released, exported, audited, or archived."
        ),
        profiles=("governed", "production"),
        facets=(
            "approval",
            "override",
            "signing",
            "release",
            "topology",
            "deployment_parity",
            "deployment_unit_refs",
            "required_service_matrix",
            "promotion_gate_evidence",
            "release_supply_chain",
            "lockfile_fingerprints",
            "generated_artifact_fingerprints",
            "sbom_attestation",
            "dirty_tree_blocker",
            "persisted_state_migration",
            "compatibility_fixtures",
            "historical_decision_replay",
            "quarantine_shim_lifecycle",
            "generated_surface_drift",
            "runbook_automation",
            "manual_gate_inventory",
            "retention_deletion_replay",
            "retention_replay_matrix",
            "deletion_minimization_scenarios",
            "connector_acquisition",
            "plugin_capability_isolation",
            "dependency_rights",
            "provider_source_risk",
            "external_evidence_provenance",
            "public_export",
            "public_export_semantic_preservation",
            "prov_slsa_archive",
            "standalone_verifier",
            "archive_replay",
            "deterministic_replay_manifest",
            "rule_evolution_registry",
            "typed_replay_drift",
            "local_client_compliance",
            "offline_mutation_authority",
            "collaboration_attribution",
            "assistant_composer_provenance",
            "bureaucratic_rendering_export",
            "client_persistence_privacy",
            "trusted_authority_fields",
            "authority_spoofing_controls",
            "shared_cas_evidence_graph",
            "tenant_scoped_cas_ownership",
            "tool_transcript_authority",
            "compaction_audit",
        ),
    ),
    _family(
        "best_in_class_benchmarking.v1",
        title="Best-in-class benchmarking",
        producer_owner="team-science-quality",
        applicability=PolicyDesignCaseRecordApplicability.PROFILE_SCOPED,
        evidence_kind=PolicyDesignCaseApplicabilityEvidenceKind.AUTHORITY_PROFILE_SCOPE,
        evidence_reason=(
            "Benchmarking and proportionality evidence is authority-profile scoped "
            "until a domain benchmark suite is selected."
        ),
        profiles=("governed", "production"),
        facets=(
            "external_audit",
            "human_team_benchmark",
            "reversal_metrics",
            "retraction_metrics",
            "calibration_metrics",
            "claim_substantiation",
            "triangulation",
            "operator_time_to_root_cause",
            "cost_proportionality_metrics",
            "run_cost_proportionality_ledger",
            "runtime_performance_budget",
            "foundry_cost_model",
            "scientist_budget",
            "doe_search_budget",
            "provider_cost",
            "elapsed_time_budget",
            "human_review_burden",
            "evidence_depth_budget",
        ),
    ),
    _family(
        "formal_substrate_invariant_spec.v1",
        title="Formal substrate invariant specification",
        producer_owner="team-quality-closeout",
        applicability=PolicyDesignCaseRecordApplicability.PROFILE_SCOPED,
        evidence_kind=PolicyDesignCaseApplicabilityEvidenceKind.AUTHORITY_PROFILE_SCOPE,
        evidence_reason=(
            "Formal or model-checked invariant specs are required for closeout-critical "
            "authority paths and can otherwise be represented by typed blockers."
        ),
        profiles=("production",),
        facets=(
            "authority_ordering",
            "phase_barriers",
            "same_input_closure",
            "cas_event_reconciliation",
            "terminal_readiness",
        ),
    ),
)

DEFAULT_POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_BINDINGS = (
    _substrate_binding(
        "PDD-019",
        title="Serious-profile degradation and fallback boundaries",
        record_family_id="capability_mode_and_fallback_selection.v1",
        facets=("mode_ledger", "fallback_degradation_ledger"),
        runtime_records=(
            "src/polisyos/runtime/quality/effective_mode.py",
            "src/polisyos/runtime/quality/degradation.py",
        ),
        test_paths=(
            "tests/unit/runtime/quality/test_effective_mode.py",
            "tests/unit/runtime/quality/test_degradation.py",
        ),
    ),
    _substrate_binding(
        "PDD-031",
        title="Replay reproduction semantics",
        record_family_id="publication_trust_and_external_governance.v1",
        facets=(
            "deterministic_replay_manifest",
            "rule_evolution_registry",
            "typed_replay_drift",
        ),
        runtime_records=(
            "src/polisyos/runtime/quality/replay.py",
            "src/polisyos/runtime/quality/rule_evolution.py",
            "src/polisyos/runtime/quality/public_export.py",
        ),
        test_paths=(
            "tests/unit/runtime/quality/test_replay.py",
            "tests/unit/runtime/quality/test_rule_evolution.py",
            "tests/unit/runtime/quality/test_public_export.py",
        ),
    ),
    _substrate_binding(
        "PDD-032",
        title="Resilience observed-versus-modeled evidence",
        record_family_id="implementation_monitoring_and_evaluation.v1",
        facets=("resilience_matrix", "observed_vs_modeled_resilience"),
        runtime_records=(
            "tools/quality/testing/runtime_resilience_matrix.py",
            "src/polisyos/runtime/quality/scorecard.py",
        ),
        test_paths=("tests/repo_quality/tools/test_runtime_resilience_matrix.py",),
    ),
    _substrate_binding(
        "PDD-039",
        title="Trusted versus untrusted authority fields",
        record_family_id="publication_trust_and_external_governance.v1",
        facets=("trusted_authority_fields", "authority_spoofing_controls"),
        runtime_records=(
            "src/polisyos/runtime/quality/authority.py",
            "src/polisyos/runtime/quality/authority_reconciliation.py",
            "src/polisyos/runtime/quality/source_truth.py",
            "src/polisyos/runtime/quality/scorecard.py",
        ),
        test_paths=("tests/unit/runtime/quality/test_authority_spoofing.py",),
    ),
    _substrate_binding(
        "PDD-040",
        title="Crash, retry, and partial-state evidence consistency",
        record_family_id="integrity_self_fmea_and_maturity.v1",
        facets=("partial_state_consistency", "retry_reconciliation"),
        runtime_records=(
            "src/polisyos/runtime/http/services/control_plane_store.py",
            "src/polisyos/runtime/quality/authority_reconciliation.py",
            "src/polisyos/runtime/quality/diagnostic_events.py",
        ),
        test_paths=("tests/unit/runtime/quality/test_crash_retry_partial_state.py",),
    ),
    _substrate_binding(
        "PDD-041",
        title="Multi-tenant shared-CAS deep evidence graph",
        record_family_id="publication_trust_and_external_governance.v1",
        facets=("shared_cas_evidence_graph", "tenant_scoped_cas_ownership"),
        runtime_records=(
            "src/polisyos/core/artifacts/store.py",
            "src/polisyos/core/artifacts/ownership.py",
            "src/polisyos/runtime/quality/public_export.py",
        ),
        test_paths=("tests/unit/runtime/quality/test_multi_tenant_shared_cas.py",),
    ),
    _substrate_binding(
        "PDD-067",
        title="Public export semantic preservation",
        record_family_id="publication_trust_and_external_governance.v1",
        facets=("public_export", "public_export_semantic_preservation"),
        runtime_records=(
            "src/polisyos/runtime/quality/public_export.py",
            "src/polisyos/runtime/quality/projection_semantics.py",
        ),
        test_paths=("tests/unit/runtime/quality/test_public_export.py",),
    ),
    _substrate_binding(
        "PDD-071",
        title="Effective runtime configuration and environment provenance",
        record_family_id="capability_mode_and_fallback_selection.v1",
        facets=("effective_configuration_ledger", "environment_provenance"),
        runtime_records=(
            "src/polisyos/runtime/quality/effective_mode.py",
            "src/polisyos/runtime/quality/attestation.py",
        ),
        test_paths=(
            "tests/unit/runtime/quality/test_effective_mode.py",
            "tests/unit/runtime/quality/test_attestation.py",
        ),
    ),
    _substrate_binding(
        "PDD-084",
        title="Tool-loop transcript, compaction, and tool-result authority",
        record_family_id="publication_trust_and_external_governance.v1",
        facets=("tool_transcript_authority", "compaction_audit"),
        runtime_records=(
            "src/polisyos/runtime/quality/prompt_tool_ledger.py",
            "src/polisyos/scientist/orchestration/llm/provider_verification.py",
        ),
        test_paths=("tests/unit/runtime/quality/test_prompt_tool_ledger.py",),
    ),
    _substrate_binding(
        "PDD-086",
        title="Synthetic-world, simulation, and counterfactual evidence boundary",
        record_family_id="method_selection_and_validity.v1",
        facets=("simulation_boundary_ledger", "evidence_mode_ledger"),
        runtime_records=(
            "src/polisyos/runtime/quality/evidence_line.py",
            "src/polisyos/foundry/validation/causal_validity.py",
        ),
        test_paths=(
            "tests/unit/runtime/quality/test_evidence_line_model.py",
            "tests/unit/foundry/validation/test_causal_validity.py",
        ),
        owner="team-science-quality",
    ),
)

_RUNTIME_RECORD_FAMILY_SOURCE_KEYS: dict[str, tuple[str, ...]] = {
    "intent_authoring_and_capture_risk.v1": (
        "intent_envelope",
        "policy_intent",
        "requester_capture_challenge_results",
    ),
    "capability_mode_and_fallback_selection.v1": (
        "capability_ledger",
        "effective_mode",
        "degradation_ledger",
        "dormant_capability_inventory",
        "skip_causality_ledger",
    ),
    "concept_and_jurisdiction_spine.v1": (
        "policy_design_concept_spine_boundary",
        "policy_design_jurisdiction_spine_boundary",
        "nodes",
        "concept_spine",
        "jurisdiction_spine",
    ),
    "legal_authority_and_competence.v1": (
        "jurisdiction_spine",
        "normative_evidence",
        "normative_applicability_report",
        "legal_authority",
    ),
    "data_source_semantic_lineage.v1": (
        "data_forge_snapshot_binding_boundary",
        "source_selection_audit",
        "fabric_source_selection_audit",
        "data_forge_snapshot_binding",
        "data_source_semantic_lineage",
    ),
    "scholar_academic_evidence.v1": (
        "scholar_academic_evidence_boundary",
        "scholar_academic_evidence",
        "scholar_evidence",
        "literature_evidence",
    ),
    "numeric_time_and_geography_semantics.v1": (
        "concept_spine",
        "nodes",
        "numerical_semantics",
        "freshness_policy_time_semantics",
    ),
    "method_selection_and_validity.v1": (
        "method_quality",
        "foundry_method_report",
        "foundry_method_evidence",
        "method_selection_and_validity",
    ),
    "evidence_portfolio_and_synthesis.v1": (
        "evidence_portfolios",
        "evidence_portfolio",
        "evidence_synthesis_report",
        "synthesis_reports",
    ),
    "structured_judgement_and_consultation.v1": (
        "structured_judgement",
        "structured_judgement_records",
        "consultation_records",
        "consultation_evidence",
    ),
    "options_objectives_and_tradeoffs.v1": (
        "options_objectives_tradeoffs",
        "objectives_tradeoffs",
        "objective_tradeoff_refs",
    ),
    "claim_argument_evidence_case.v1": (
        "claim_registry",
        "final_major_claims",
        "claim_arguments",
        "arguments",
        "warrants",
    ),
    "implementation_monitoring_and_evaluation.v1": (
        "implementation_monitoring_evaluation",
        "implementation_monitoring",
        "monitoring_plan",
        "ddm_post_market_evidence",
        "resilience_report",
    ),
    "human_oversight_independence_and_review.v1": (
        "human_oversight",
        "human_review",
        "human_review_authority",
        "independence_review",
        "pass1b_tenant_cas_approval_governance",
    ),
    "integrity_self_fmea_and_maturity.v1": (
        "case_maturity_profile",
        "self_fmea",
        "non_adversarial_self_fmea",
        "partial_state_consistency",
        "substrate_residual_verification",
    ),
    "lifecycle_ex_post_and_calibration.v1": (
        "case_lifecycle",
        "continuous_governance_stale",
        "continuous_governance_reissue",
        "continuous_governance_supersede",
        "continuous_governance_withdraw",
        "ex_post_learning",
    ),
    "publication_trust_and_external_governance.v1": (
        "publication_trust",
        "public_export",
        "external_audit",
        "replay_manifest",
        "rule_evolution",
        "rule_evolution_registry",
        "pass1b_tenant_cas_approval_governance",
    ),
    "best_in_class_benchmarking.v1": (
        "benchmarking",
        "run_cost_proportionality_ledger",
        "runtime_performance_budget",
        "cost_proportionality",
    ),
    "formal_substrate_invariant_spec.v1": (
        "formal_invariants",
        "formal_substrate_invariant_spec",
        "phase_barrier_records",
        "same_input_closure",
    ),
}

_RUNTIME_RESIDUAL_BOUNDARY_KEYS_BY_FAMILY: dict[str, tuple[str, ...]] = {
    "concept_and_jurisdiction_spine.v1": (
        "policy_design_concept_spine_boundary",
        "policy_design_jurisdiction_spine_boundary",
    ),
    "data_source_semantic_lineage.v1": ("data_forge_snapshot_binding_boundary",),
    "scholar_academic_evidence.v1": ("scholar_academic_evidence_boundary",),
}


def compile_policy_design_case_runtime_record_families(
    case: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile minimum SDD record families from runtime-owned PDC surfaces.

    The compiler intentionally does not treat profile metadata or a top-level
    `status=pass` as authority. Families with no runtime producer surface become
    typed blockers or out-of-scope rows, so downstream readiness gates can read a
    concrete family ledger instead of inferring from summary status.
    """

    if not isinstance(case, Mapping):
        raise TypeError("Policy Design Case compilation requires a mapping payload.")

    compiled = dict(case)
    compiled.update(_policy_design_case_residual_boundary_records(compiled))
    case_id = _text_field(compiled.get("case_id")) or "policy-design-case"
    run_id = _text_field(compiled.get("run_id")) or "run-unknown"
    job_id = _text_field(compiled.get("job_id")) or "job-unknown"
    tenant_id = _text_field(compiled.get("tenant_id")) or "tenant-unknown"
    profile = _status(
        compiled.get("effective_execution_profile")
        or compiled.get("authority_profile")
        or compiled.get("execution_profile")
        or "research"
    )
    compilation_ref = _case_compilation_ref(compiled)
    compilation_event_ref = _case_compilation_event_ref(compiled, case_id=case_id)

    family_rows: list[dict[str, Any]] = []
    runtime_records: list[dict[str, Any]] = []
    blocked_family_ids: list[str] = []
    out_of_scope_family_ids: list[str] = []

    for registry_row in DEFAULT_POLICY_DESIGN_CASE_RECORD_REGISTRY:
        registry = registry_row.as_dict()
        family_id = registry["family_id"]
        source_keys = _RUNTIME_RECORD_FAMILY_SOURCE_KEYS.get(family_id, ())
        source_refs = _family_runtime_source_refs(compiled, source_keys)
        residual_boundary_failures = _family_residual_boundary_failures(
            compiled,
            family_id,
        )
        family_status = (
            "blocked"
            if residual_boundary_failures
            else (
                "present"
                if source_refs
                else _policy_family_absence_status(
                    registry,
                    profile=profile,
                )
            )
        )
        residual_boundary_refs = _residual_boundary_refs(residual_boundary_failures)
        runtime_refs = source_refs or residual_boundary_refs or (compilation_ref,)
        family_event_ref = _first_runtime_event_ref(compiled, source_keys) or (
            f"event://policy-design-case/record-family-compilation/{case_id}/{family_id}"
        )
        authority_envelope = {
            "authority_role": "reader_authority",
            "provenance_kind": "runtime_derived"
            if family_status == "present"
            else "runtime_blocker",
            "cas_ref": runtime_refs[0],
            "runtime_event_ref": family_event_ref,
        }
        family_row: dict[str, Any] = {
            "family_id": family_id,
            "status": family_status,
            "schema_owner": "team-runtime-quality",
            "producer_owner": registry["producer_owner"],
            "reader_owner": registry["reader_owner"],
            "schema_name": registry["schema_name"],
            "scorecard_gate": registry["scorecard_gate"],
            "readiness_gate": RECORD_FAMILY_COVERAGE_READINESS_CHECK,
            "readiness_check": RECORD_FAMILY_COVERAGE_READINESS_CHECK,
            "runtime_refs": list(runtime_refs),
            "source_keys": list(source_keys),
            "authority_envelope": authority_envelope,
        }
        governance_surfaces = _governance_surfaces_for_family(family_id)
        if governance_surfaces:
            family_row["governance_surfaces"] = list(governance_surfaces)

        if family_status == "present":
            runtime_records.append(
                _compiled_runtime_record(
                    case_id=case_id,
                    run_id=run_id,
                    job_id=job_id,
                    tenant_id=tenant_id,
                    family_id=family_id,
                    registry=registry,
                    source_keys=source_keys,
                    source_refs=runtime_refs,
                    runtime_event_ref=family_event_ref,
                )
            )
        else:
            policy = (
                _typed_family_residual_boundary_policy(
                    family_id=family_id,
                    profile=profile,
                    boundary_failures=residual_boundary_failures,
                    evidence_ref=runtime_refs[0],
                    runtime_event_ref=family_event_ref,
                )
                if residual_boundary_failures
                else _typed_family_absence_policy(
                    family_id=family_id,
                    status=family_status,
                    profile=profile,
                    evidence_ref=compilation_ref,
                    runtime_event_ref=family_event_ref,
                )
            )
            family_row["typed_authority_policy"] = policy
            if family_status == "blocked":
                blocked_family_ids.append(family_id)
            else:
                out_of_scope_family_ids.append(family_id)

        family_rows.append(family_row)

    compiled["record_families"] = family_rows
    compiled["records"] = runtime_records
    compiled["record_family_compilation"] = {
        "schema_version": RUNTIME_RECORD_FAMILY_COMPILATION_SCHEMA_VERSION,
        "status": "blocked" if blocked_family_ids else "pass",
        "compiler": "polisyos.runtime.quality.policy_design_case",
        "case_id": case_id,
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "effective_execution_profile": profile,
        "runtime_record_count": len(runtime_records),
        "record_family_count": len(family_rows),
        "blocked_family_ids": blocked_family_ids,
        "out_of_scope_family_ids": out_of_scope_family_ids,
        "evidence_ref": compilation_ref,
        "runtime_event_ref": compilation_event_ref,
    }
    compiled["status"] = "blocked" if blocked_family_ids else "pass"
    return compiled


def _policy_design_case_residual_boundary_records(
    case: Mapping[str, Any],
) -> dict[str, Any]:
    from polisyos.runtime.quality.concept_spine import (
        build_policy_design_concept_spine_boundary_record,
    )
    from polisyos.runtime.quality.data_forge_binding import (
        normalize_data_forge_snapshot_binding_report,
    )
    from polisyos.runtime.quality.policy_design_jurisdiction_spine import (
        build_policy_design_jurisdiction_spine_boundary_record,
    )
    from polisyos.runtime.quality.scholar_academic_evidence import (
        build_scholar_academic_evidence_boundary_record,
    )

    concept_boundary = build_policy_design_concept_spine_boundary_record(
        _concept_spine_from_case(case)
    )
    jurisdiction = case.get("jurisdiction_spine")
    jurisdiction_boundary = build_policy_design_jurisdiction_spine_boundary_record(
        jurisdiction if isinstance(jurisdiction, Mapping) else None
    )
    data_forge_report = case.get("data_forge_snapshot_binding")
    data_forge_boundary = _data_forge_snapshot_boundary_record(
        normalize_data_forge_snapshot_binding_report(
            data_forge_report if isinstance(data_forge_report, Mapping) else None
        )
    )
    scholar_report = case.get("scholar_academic_evidence") or case.get("scholar_evidence")
    scholar_boundary = build_scholar_academic_evidence_boundary_record(
        scholar_report if isinstance(scholar_report, Mapping) else None
    )
    boundaries = [
        data_forge_boundary,
        scholar_boundary,
        concept_boundary,
        jurisdiction_boundary,
    ]
    return {
        "data_forge_snapshot_binding_boundary": data_forge_boundary,
        "scholar_academic_evidence_boundary": scholar_boundary,
        "policy_design_concept_spine_boundary": concept_boundary,
        "policy_design_jurisdiction_spine_boundary": jurisdiction_boundary,
        "residual_spine_boundaries": boundaries,
    }


def _data_forge_snapshot_boundary_record(
    normalized: Mapping[str, Any],
) -> dict[str, Any]:
    status = _status(normalized.get("status") or "fail")
    issues = _mapping_rows(normalized.get("issues"))
    blockers = _mapping_rows(normalized.get("blockers"))
    evidence_ref = _first_artifact_ref(_runtime_refs_from_value(normalized)) or _derived_ref(
        "data-forge-snapshot-boundary",
        normalized,
    )
    runtime_event_ref = _first_runtime_event_ref(
        {"data_forge_snapshot_binding": normalized},
        ("data_forge_snapshot_binding",),
    ) or f"event://policy-design-case/data-forge-snapshot-boundary/{evidence_ref}"
    return {
        "schema_version": "policyos.runtime.policy_design_case.data_forge_snapshot_boundary.v1",
        "record_id": "policy-design-data-forge-snapshot-boundary",
        "record_family": "data_source_semantic_lineage.v1",
        "status": "failed" if issues else ("blocked" if status == "blocked" else "pass"),
        "producer_owner": "team-data-forge",
        "reader_owner": "team-runtime-quality",
        "scorecard_gate": "data_forge_snapshot_binding_valid",
        "readiness_gate": "policy_design_case.residual_spine_boundaries",
        "evidence_ref": evidence_ref,
        "cas_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
        "blockers": blockers,
        "issues": issues,
        "runtime_authority_envelope": {
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_blocker"
            if issues or status == "blocked"
            else "runtime_derived",
            "cas_ref": evidence_ref,
            "runtime_event_ref": runtime_event_ref,
        },
    }


def _concept_spine_from_case(case: Mapping[str, Any]) -> Mapping[str, Any] | None:
    concept = case.get("concept_spine")
    if isinstance(concept, Mapping):
        return concept
    nodes = case.get("nodes")
    if isinstance(nodes, list | tuple):
        for node in nodes:
            if isinstance(node, Mapping) and str(node.get("node_type") or "") == "concept_spine":
                return node
    return None


def _family_residual_boundary_failures(
    case: Mapping[str, Any],
    family_id: str,
) -> tuple[dict[str, Any], ...]:
    failures: list[dict[str, Any]] = []
    for key in _RUNTIME_RESIDUAL_BOUNDARY_KEYS_BY_FAMILY.get(family_id, ()):
        boundary = case.get(key)
        if not isinstance(boundary, Mapping):
            continue
        if _status(boundary.get("status")) != "pass":
            failures.append(dict(boundary))
    return tuple(failures)


def _residual_boundary_refs(boundaries: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    refs: list[str] = []
    for boundary in boundaries:
        refs.extend(_runtime_refs_from_value(boundary))
    return tuple(dict.fromkeys(refs))


def _typed_family_residual_boundary_policy(
    *,
    family_id: str,
    profile: str,
    boundary_failures: tuple[dict[str, Any], ...],
    evidence_ref: str,
    runtime_event_ref: str,
) -> dict[str, Any]:
    codes = []
    for boundary in boundary_failures:
        codes.extend(
            str(issue.get("code"))
            for issue in _mapping_rows(boundary.get("issues"))
            if str(issue.get("code") or "").strip()
        )
        codes.extend(
            str(blocker.get("code"))
            for blocker in _mapping_rows(boundary.get("blockers"))
            if str(blocker.get("code") or "").strip()
        )
    deduped_codes = list(dict.fromkeys(codes))
    return {
        "policy_code": (
            f"policy_design_case.{family_id.removesuffix('.v1')}.residual_boundary_blocked"
        ),
        "status": "blocked",
        "profile": profile,
        "reason": (
            "A residual upstream producer boundary failed or emitted a typed blocker "
            "before Policy Design Case record-family compilation."
        ),
        "boundary_record_ids": [
            str(boundary.get("record_id") or "unknown_boundary")
            for boundary in boundary_failures
        ],
        "issue_codes": deduped_codes,
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
    }


def _compiled_runtime_record(
    *,
    case_id: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    family_id: str,
    registry: Mapping[str, Any],
    source_keys: tuple[str, ...],
    source_refs: tuple[str, ...],
    runtime_event_ref: str,
) -> dict[str, Any]:
    slug = family_id.removesuffix(".v1").replace("_", "-")
    evidence_ref = _first_artifact_ref(source_refs) or source_refs[0]
    return {
        "record_id": f"pdc-{slug}-runtime-record",
        "case_id": case_id,
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "family_id": family_id,
        "record_family": family_id,
        "schema_name": registry["schema_name"],
        "schema_version": registry["schema_name"],
        "producer_owner": registry["producer_owner"],
        "reader_owner": registry["reader_owner"],
        "readiness_gate": RECORD_FAMILY_COVERAGE_READINESS_CHECK,
        "readiness_check": RECORD_FAMILY_COVERAGE_READINESS_CHECK,
        "source_keys": list(source_keys),
        "source_refs": list(source_refs),
        "evidence_ref": evidence_ref,
        "cas_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
        "authority_envelope": {
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_derived",
            "cas_ref": evidence_ref,
            "runtime_event_ref": runtime_event_ref,
        },
    }


def _policy_family_absence_status(
    registry: Mapping[str, Any],
    *,
    profile: str,
) -> str:
    evidence = registry.get("applicability_evidence")
    profiles = set(_string_list(evidence.get("profiles") if isinstance(evidence, Mapping) else ()))
    applicability = str(registry.get("applicability") or "").strip()
    if applicability in {"profile_scoped", "not_applicable"} and profile not in profiles:
        return "out_of_scope"
    return "blocked"


def _typed_family_absence_policy(
    *,
    family_id: str,
    status: str,
    profile: str,
    evidence_ref: str,
    runtime_event_ref: str,
) -> dict[str, Any]:
    return {
        "policy_code": f"policy_design_case.{family_id.removesuffix('.v1')}.{status}",
        "status": status,
        "profile": profile,
        "reason": (
            "No runtime producer surface was available for this minimum Policy "
            "Design Case family during record-family compilation."
        )
        if status == "blocked"
        else (
            "The active authority profile leaves this record family out of scope "
            "until governed or production publication semantics apply."
        ),
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
    }


def _family_runtime_source_refs(
    case: Mapping[str, Any],
    source_keys: tuple[str, ...],
) -> tuple[str, ...]:
    refs: list[str] = []
    for key in source_keys:
        if key not in case:
            continue
        value = case.get(key)
        if not _has_meaningful_runtime_surface(value):
            continue
        refs.extend(_runtime_refs_from_value(value))
    return tuple(dict.fromkeys(refs))


def _first_runtime_event_ref(
    case: Mapping[str, Any],
    source_keys: tuple[str, ...],
) -> str | None:
    for key in source_keys:
        if key not in case or not _has_meaningful_runtime_surface(case.get(key)):
            continue
        for ref in _runtime_refs_from_value(case.get(key)):
            if _coverage_runtime_event_ref(ref):
                return ref
    authority = case.get("runtime_authority") or case.get("authority_chain")
    if isinstance(authority, Mapping) and _coverage_runtime_event_ref(
        authority.get("runtime_event_ref")
    ):
        return str(authority["runtime_event_ref"]).strip()
    return None


def _case_compilation_ref(case: Mapping[str, Any]) -> str:
    authority = case.get("runtime_authority") or case.get("authority_chain")
    if isinstance(authority, Mapping):
        for key in ("cas_ref", "evidence_ref", "same_input_closure_ref"):
            value = authority.get(key)
            if _coverage_runtime_artifact_ref(value):
                return str(value).strip()
    for ref in _runtime_refs_from_value(case):
        if _coverage_runtime_artifact_ref(ref):
            return ref
    digest = hashlib.sha256(
        json.dumps(
            {
                "case_id": case.get("case_id"),
                "run_id": case.get("run_id"),
                "job_id": case.get("job_id"),
                "tenant_id": case.get("tenant_id"),
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def _derived_ref(prefix: str, value: object) -> str:
    digest = hashlib.sha256(
        json.dumps({prefix: value}, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def _case_compilation_event_ref(case: Mapping[str, Any], *, case_id: str) -> str:
    authority = case.get("runtime_authority") or case.get("authority_chain")
    if isinstance(authority, Mapping) and _coverage_runtime_event_ref(
        authority.get("runtime_event_ref")
    ):
        return str(authority["runtime_event_ref"]).strip()
    return f"event://policy-design-case/record-family-compilation/{case_id}"


def _first_artifact_ref(refs: tuple[str, ...]) -> str | None:
    for ref in refs:
        if _coverage_runtime_artifact_ref(ref):
            return ref
    return None


def _runtime_refs_from_value(value: object) -> tuple[str, ...]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(item, str) and (
                key.endswith("_ref")
                or key.endswith("_refs")
                or key in {"cas_ref", "evidence_ref", "record_ref", "ledger_ref"}
            ):
                text = item.strip()
                if _coverage_runtime_artifact_ref(text) or _coverage_runtime_event_ref(text):
                    refs.append(text)
            elif isinstance(item, list | tuple | Mapping):
                refs.extend(_runtime_refs_from_value(item))
    elif isinstance(value, list | tuple):
        for item in value:
            refs.extend(_runtime_refs_from_value(item))
    elif isinstance(value, str):
        text = value.strip()
        if _coverage_runtime_artifact_ref(text) or _coverage_runtime_event_ref(text):
            refs.append(text)
    return tuple(dict.fromkeys(refs))


def _has_meaningful_runtime_surface(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, list | tuple | set):
        return any(_has_meaningful_runtime_surface(item) for item in value)
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _governance_surfaces_for_family(family_id: str) -> tuple[str, ...]:
    return tuple(
        surface
        for surface, required_family in (
            POLICY_DESIGN_CASE_GOVERNANCE_RECORD_FAMILY_REQUIREMENTS.items()
        )
        if required_family == family_id
    )
