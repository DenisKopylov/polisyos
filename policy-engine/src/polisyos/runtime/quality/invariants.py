"""Production invariant registry loading and validation.

The registry is the runtime-readable ownership contract for serious closeout
invariants. It intentionally validates both row shape and the named reader /
enforcer mappings so scorecard, readiness, runtime-event, and projection policy
semantics stay machine-checkable.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REGISTRY_RELATIVE_PATH = Path("architecture/production_quality/invariant_registry.toml")
DEFAULT_REGISTRY_PATH = REPO_ROOT / DEFAULT_REGISTRY_RELATIVE_PATH

SCHEMA_VERSION = "policyos.production_invariant_registry.validation.v1"
TOOL_NAME = "runtime.quality.production-invariant-registry"

REQUIRED_INVARIANT_FIELDS = frozenset(
    {
        "invariant_id",
        "minimum_closeout_gate",
        "pql_id",
        "final_owner",
        "producer_owners",
        "runtime_event_names",
        "required_artifact_kinds",
        "required_ref_keys",
        "evidence_classes",
        "allowed_provenance_kinds",
        "required_schema_contracts",
        "scorecard_gate_names",
        "readiness_check",
        "approval_policy",
        "override_policy",
        "non_overridable_blockers",
        "dashboard_projection_policy",
        "public_artifact_policy",
        "conflict_policy",
        "failure_code",
        "diagnostic_owner",
        "dependencies",
        "consumers",
        "next_diagnostic_command",
        "negative_tests",
    }
)
REQUIRED_STRING_INVARIANT_FIELDS = frozenset(
    {
        "invariant_id",
        "minimum_closeout_gate",
        "pql_id",
        "final_owner",
        "readiness_check",
        "approval_policy",
        "override_policy",
        "dashboard_projection_policy",
        "public_artifact_policy",
        "conflict_policy",
        "failure_code",
        "diagnostic_owner",
        "next_diagnostic_command",
    }
)
REQUIRED_LIST_INVARIANT_FIELDS = frozenset(
    {
        "producer_owners",
        "runtime_event_names",
        "required_artifact_kinds",
        "required_ref_keys",
        "evidence_classes",
        "allowed_provenance_kinds",
        "required_schema_contracts",
        "scorecard_gate_names",
        "non_overridable_blockers",
        "consumers",
        "negative_tests",
    }
)
OPTIONAL_LIST_INVARIANT_FIELDS = frozenset({"dependencies"})

FIELD_MISSING_CODES = {
    "final_owner": "invariant_final_owner_missing",
    "override_policy": "invariant_override_policy_missing",
    "dashboard_projection_policy": "invariant_dashboard_projection_policy_missing",
    "failure_code": "invariant_failure_code_missing",
}
FINAL_OWNER_MULTI_SEPARATORS = (",", "|", ";", " + ", " and ")
PROJECTION_FINAL_OWNER_MARKERS = (
    "dashboard",
    "projection",
    "public_artifact",
    "bundle",
    "canary_packaging",
)

MINIMUM_CLOSEOUT_GATES: Mapping[str, str] = {
    "serious_canary_runtime_refs": (
        "Every serious canary emits Lex, Fabric, Foundry, grounding, and conflict refs."
    ),
    "scorecard_persisted_runtime_refs": (
        "Scorecard is built from persisted runtime refs and included in the evidence bundle."
    ),
    "final_policy_major_claims_grounded": ("Final policy major claims are grounded or blocked."),
    "metric_taxonomy_unknown_metrics_fail": (
        "Unknown metrics fail before Trinity with suggestions."
    ),
    "benchmark_authority_packs": (
        "Public and hidden benchmark authority packs exist and pass contamination guards."
    ),
    "performance_budget_evidence": ("Performance budget evidence is included in canary bundles."),
    "tenant_scoped_artifact_ownership": (
        "Tenant-scoped artifact ownership is enforced for governed/production access."
    ),
    "production_approval_or_signed_override": (
        "Production approval requires pass-quality evidence or a signed override."
    ),
    "continuous_governance_lifecycle": (
        "Continuous governance can stale/reissue/withdraw published decisions."
    ),
    "production_data_quality_reports": (
        "Production data quality reports cover drift, leakage, coverage, recency, and validity."
    ),
    "causal_statistical_method_reports": (
        "Causal/statistical method reports pass known-answer, placebo, negative-control, "
        "sensitivity, uncertainty, and power gates."
    ),
    "security_abuse_resistance_gates": (
        "Security and abuse-resistance gates fail closed for injection, malicious artifacts, "
        "unsafe rendering, traversal, and secret exfiltration."
    ),
    "privacy_compliance_evidence": (
        "Privacy, licensing, retention, jurisdiction, minimization, redaction, and public-export "
        "compliance evidence is present."
    ),
    "deterministic_replay_or_typed_drift": (
        "Deterministic replay can reproduce serious runs or produce typed bounded drift."
    ),
    "resilience_readiness_lanes": (
        "Load, soak, retry-storm, provider-brownout, CAS-pressure, queue-saturation, and "
        "dashboard degradation lanes pass readiness gates."
    ),
    "human_review_calibration_evidence": (
        "Human review has calibration evidence for agreement, override correctness, burden, "
        "escalation, unresolved disagreement, and reviewer attribution."
    ),
    "provider_model_quality_drift": (
        "Provider/model quality drift is monitored across schema, grounding, faithfulness, "
        "disagreement, latency, cost, provider errors, and quality."
    ),
    "serious_effective_mode_allowed": (
        "Effective mode ledgers block dev, fixture, simulated, mock, and warn-accepted "
        "paths from satisfying serious closeout."
    ),
    "final_decision_artifact_quality": (
        "Final decision artifacts pass compiler-grade checks for uncertainty, tradeoffs, "
        "distributional impact, feasibility, budget, stakeholders, risk, monitoring, and "
        "residual uncertainty."
    ),
    "serious_phase_barriers_closed": (
        "Serious run state transitions, scorecard readiness, approval readiness, final "
        "artifacts, public exports, and canary bundle closeout are blocked until ADR-0148 "
        "phase barriers pass or emit typed blockers."
    ),
    "closeout_matrix_dashboard_api_smoke": (
        "Deterministic canary matrix, dashboard smoke, runtime API contract check, and local "
        "integration stack smoke pass."
    ),
}

KNOWN_SCORECARD_GATES = frozenset(
    {
        "causal_statistical_validity_present",
        "conflict_check_present",
        "continuous_governance_reissue_report_present",
        "continuous_governance_stale_report_present",
        "continuous_governance_supersede_report_present",
        "continuous_governance_withdraw_report_present",
        "data_materialization_refs_present",
        "decision_artifact_quality_present",
        "drift_explanation_present",
        "execution_completed",
        "effective_mode_allowed",
        "fabric_retrieval_trace_present",
        "foundry_method_evidence_present",
        "human_review_calibration_present",
        "llm_model_variants_present",
        "llm_schema_validation_recorded",
        "llm_usage_accounting_present",
        "normative_evidence_present",
        "policy_grounding_matrix_present",
        "privacy_compliance_report_present",
        "production_data_quality_present",
        "provider_model_quality_ledger_passed",
        "provider_preflight_recorded",
        "replay_manifest_present",
        "resilience_matrix_present",
        "scientist_workflow_report_passed",
        "security_assurance_report_passed",
    }
)
KNOWN_READINESS_CHECKS = frozenset(
    {
        "production_quality.runtime_required_refs",
        "production_quality.scorecard_persisted_runtime_refs",
        "production_quality.policy_grounding",
        "production_quality.metric_taxonomy",
        "production_quality.benchmark_authority",
        "production_quality.performance_budget",
        "production_quality.tenant_artifact_ownership",
        "production_quality.approval_packet",
        "production_quality.continuous_governance_lifecycle",
        "production_quality.data_quality",
        "production_quality.causal_statistical_validity",
        "production_quality.security_assurance",
        "production_quality.privacy_compliance",
        "production_quality.replay_determinism",
        "production_quality.resilience_matrix",
        "production_quality.human_review_calibration",
        "production_quality.provider_model_quality",
        "production_quality.effective_mode_allowed",
        "production_quality.decision_artifact_quality",
        "production_quality.phase_barriers_closed",
        "production_quality.closeout_matrix_smoke",
        "layer3_gl_legal_mandate_search_readiness_gate",
    }
)
KNOWN_RUNTIME_EVENTS = frozenset(
    {
        "polisyos.runtime.evidence.normative_applicability_report.v1",
        "polisyos.runtime.evidence.fabric_retrieval_trace.v1",
        "polisyos.runtime.evidence.foundry_method_report.v1",
        "polisyos.runtime.evidence.policy_grounding_matrix.v1",
        "polisyos.runtime.evidence.conflict_check.v1",
        "polisyos.runtime.diagnostic.producer_execution.v1",
        "polisyos.runtime.diagnostic.cas_write.v1",
        "polisyos.runtime.diagnostic.ref_publication.v1",
        "polisyos.runtime.diagnostic.phase_transition.v1",
        "polisyos.runtime.diagnostic.blocker.v1",
        "polisyos.runtime.diagnostic.fallback_degradation.v1",
        "polisyos.runtime.diagnostic.schema_migration.v1",
        "polisyos.runtime.diagnostic.scorecard_gate_read.v1",
        "polisyos.runtime.diagnostic.readiness_closeout.v1",
        "polisyos.runtime.diagnostic.approval_decision.v1",
        "polisyos.runtime.diagnostic.dashboard_projection.v1",
        "polisyos.runtime.diagnostic.public_artifact_publication.v1",
        "polisyos.runtime.diagnostic.replay_result.v1",
        "polisyos.runtime.diagnostic.reconciliation_result.v1",
        "polisyos.runtime.diagnostic.governance_lifecycle_decision.v1",
        "producer_execution",
        "cas_write",
        "ref_publication",
        "phase_transition",
        "blocker",
        "polisyos.runtime.diagnostic.effective_mode.v1",
        "effective_mode",
        "fallback_degradation",
        "schema_migration",
        "scorecard_gate_read",
        "readiness_closeout",
        "approval_decision",
        "dashboard_projection",
        "public_artifact_publication",
        "replay_result",
        "reconciliation_result",
        "governance_lifecycle_decision",
    }
)


@dataclass(frozen=True)
class InvariantRegistryIssue:
    """One deterministic registry validation finding."""

    code: str
    invariant_id: str
    field: str
    message: str
    value: object | None = None
    severity: str = "error"

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "severity": self.severity,
            "invariant_id": self.invariant_id,
            "field": self.field,
            "message": self.message,
        }
        if self.value is not None:
            payload["value"] = self.value
        return payload


@dataclass(frozen=True)
class InvariantRegistryValidationResult:
    """Validation result shared by runtime code, repo-quality tests, and CLI tooling."""

    status: str
    invariants: tuple[dict[str, Any], ...]
    issues: tuple[InvariantRegistryIssue, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "summary": {
                "invariant_count": len(self.invariants),
                "issue_count": len(self.issues),
            },
            "issues": [issue.as_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class ProductionInvariant:
    """Typed view of one valid production invariant registry row."""

    invariant_id: str
    minimum_closeout_gate: str
    pql_id: str
    final_owner: str
    producer_owners: tuple[str, ...]
    runtime_event_names: tuple[str, ...]
    required_artifact_kinds: tuple[str, ...]
    required_ref_keys: tuple[str, ...]
    evidence_classes: tuple[str, ...]
    allowed_provenance_kinds: tuple[str, ...]
    required_schema_contracts: tuple[str, ...]
    scorecard_gate_names: tuple[str, ...]
    readiness_check: str
    approval_policy: str
    override_policy: str
    non_overridable_blockers: tuple[str, ...]
    dashboard_projection_policy: str
    public_artifact_policy: str
    conflict_policy: str
    failure_code: str
    diagnostic_owner: str
    dependencies: tuple[str, ...]
    consumers: tuple[str, ...]
    next_diagnostic_command: str
    negative_tests: tuple[str, ...]
    raw: Mapping[str, Any]

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> ProductionInvariant:
        return cls(
            invariant_id=str(row["invariant_id"]),
            minimum_closeout_gate=str(row["minimum_closeout_gate"]),
            pql_id=str(row["pql_id"]),
            final_owner=str(row["final_owner"]),
            producer_owners=tuple(_string_list(row["producer_owners"])),
            runtime_event_names=tuple(_string_list(row["runtime_event_names"])),
            required_artifact_kinds=tuple(_string_list(row["required_artifact_kinds"])),
            required_ref_keys=tuple(_string_list(row["required_ref_keys"])),
            evidence_classes=tuple(_string_list(row["evidence_classes"])),
            allowed_provenance_kinds=tuple(_string_list(row["allowed_provenance_kinds"])),
            required_schema_contracts=tuple(_string_list(row["required_schema_contracts"])),
            scorecard_gate_names=tuple(_string_list(row["scorecard_gate_names"])),
            readiness_check=str(row["readiness_check"]),
            approval_policy=str(row["approval_policy"]),
            override_policy=str(row["override_policy"]),
            non_overridable_blockers=tuple(_string_list(row["non_overridable_blockers"])),
            dashboard_projection_policy=str(row["dashboard_projection_policy"]),
            public_artifact_policy=str(row["public_artifact_policy"]),
            conflict_policy=str(row["conflict_policy"]),
            failure_code=str(row["failure_code"]),
            diagnostic_owner=str(row["diagnostic_owner"]),
            dependencies=tuple(_string_list(row["dependencies"])),
            consumers=tuple(_string_list(row["consumers"])),
            next_diagnostic_command=str(row["next_diagnostic_command"]),
            negative_tests=tuple(_string_list(row["negative_tests"])),
            raw=dict(row),
        )


@dataclass(frozen=True)
class ProductionInvariantRegistry:
    """Loaded production invariant registry."""

    invariants: tuple[ProductionInvariant, ...]
    validation: InvariantRegistryValidationResult
    registry_path: Path

    def by_id(self, invariant_id: str) -> ProductionInvariant | None:
        for invariant in self.invariants:
            if invariant.invariant_id == invariant_id:
                return invariant
        return None

    def for_minimum_closeout_gate(
        self, minimum_closeout_gate: str
    ) -> tuple[ProductionInvariant, ...]:
        return tuple(
            invariant
            for invariant in self.invariants
            if invariant.minimum_closeout_gate == minimum_closeout_gate
        )


class InvariantRegistryError(ValueError):
    """Raised when a strict registry load finds validation errors."""

    def __init__(self, result: InvariantRegistryValidationResult) -> None:
        self.result = result
        codes = sorted({issue.code for issue in result.issues})
        super().__init__("Production invariant registry is invalid: " + ", ".join(codes))


def load_production_invariant_registry(
    *,
    repo_root: Path | str = REPO_ROOT,
    registry_path: Path | str = DEFAULT_REGISTRY_RELATIVE_PATH,
    strict: bool = True,
) -> ProductionInvariantRegistry:
    """Load and validate the production invariant registry TOML file."""

    repo_root_path = Path(repo_root).resolve()
    registry_file = _resolve(repo_root_path, Path(registry_path))
    payload = _load_toml(registry_file)
    result = validate_invariant_registry_payload(payload, repo_root=repo_root_path)
    if strict and result.issues:
        raise InvariantRegistryError(result)
    invalid_ids = {issue.invariant_id for issue in result.issues}
    invariants = tuple(
        ProductionInvariant.from_row(row)
        for row in result.invariants
        if _row_label(row, 0) not in invalid_ids
    )
    return ProductionInvariantRegistry(
        invariants=invariants,
        validation=result,
        registry_path=registry_file,
    )


def validate_invariant_registry_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | str = REPO_ROOT,
    known_scorecard_gates: set[str] | frozenset[str] = KNOWN_SCORECARD_GATES,
    known_readiness_checks: set[str] | frozenset[str] = KNOWN_READINESS_CHECKS,
    known_runtime_events: set[str] | frozenset[str] = KNOWN_RUNTIME_EVENTS,
    minimum_closeout_gates: Mapping[str, str] = MINIMUM_CLOSEOUT_GATES,
) -> InvariantRegistryValidationResult:
    """Validate a parsed registry payload."""

    repo_root_path = Path(repo_root).resolve()
    raw_invariants = payload.get("invariants")
    issues: list[InvariantRegistryIssue] = []
    invariants: list[dict[str, Any]] = []

    if not isinstance(raw_invariants, list) or not raw_invariants:
        issues.append(
            InvariantRegistryIssue(
                code="invariant_registry_missing_rows",
                invariant_id="registry",
                field="invariants",
                message="Invariant registry must define at least one [[invariants]] row.",
            )
        )
        return InvariantRegistryValidationResult(
            status="fail",
            invariants=(),
            issues=tuple(issues),
        )

    seen_ids: dict[str, int] = {}
    seen_minimum_closeout_gates: dict[str, list[str]] = {}
    for index, raw_row in enumerate(raw_invariants, start=1):
        if not isinstance(raw_row, Mapping):
            issues.append(
                InvariantRegistryIssue(
                    code="invariant_row_invalid",
                    invariant_id=f"invariants[{index}]",
                    field="invariants",
                    message="Every invariant registry row must be a TOML table.",
                )
            )
            continue
        row = dict(raw_row)
        invariants.append(row)
        label = _row_label(row, index)
        if label in seen_ids:
            issues.append(
                InvariantRegistryIssue(
                    code="invariant_id_duplicate",
                    invariant_id=label,
                    field="invariant_id",
                    message="Invariant IDs must be unique.",
                    value=label,
                )
            )
        seen_ids[label] = index
        minimum_closeout_gate = row.get("minimum_closeout_gate")
        if _non_empty_string(minimum_closeout_gate):
            seen_minimum_closeout_gates.setdefault(str(minimum_closeout_gate).strip(), []).append(
                label
            )

        issues.extend(_field_shape_issues(row, index=index))
        issues.extend(
            _mapping_issues(
                row,
                index=index,
                known_scorecard_gates=known_scorecard_gates,
                known_readiness_checks=known_readiness_checks,
                known_runtime_events=known_runtime_events,
                minimum_closeout_gates=minimum_closeout_gates,
            )
        )
        issues.extend(_negative_test_ref_issues(row, index=index, repo_root=repo_root_path))

    for gate in sorted(set(minimum_closeout_gates) - set(seen_minimum_closeout_gates)):
        issues.append(
            InvariantRegistryIssue(
                code="invariant_minimum_closeout_gate_unregistered",
                invariant_id=gate,
                field="minimum_closeout_gate",
                message="Every known Minimum Closeout Gate must have a registry row.",
                value=gate,
            )
        )
    for gate, invariant_ids in sorted(seen_minimum_closeout_gates.items()):
        if gate not in minimum_closeout_gates or len(invariant_ids) <= 1:
            continue
        issues.append(
            InvariantRegistryIssue(
                code="invariant_minimum_closeout_gate_duplicate",
                invariant_id=gate,
                field="minimum_closeout_gate",
                message=(
                    "Minimum Closeout Gate maps to multiple invariants without an "
                    "explicit many-to-one policy."
                ),
                value=invariant_ids,
            )
        )

    return InvariantRegistryValidationResult(
        status="fail" if issues else "pass",
        invariants=tuple(invariants),
        issues=tuple(issues),
    )


def build_production_invariant_registry_report(
    *,
    repo_root: Path | str = REPO_ROOT,
    registry_path: Path | str = DEFAULT_REGISTRY_RELATIVE_PATH,
) -> dict[str, Any]:
    """Build a machine-readable registry diff and validation report."""

    repo_root_path = Path(repo_root).resolve()
    registry_file = _resolve(repo_root_path, Path(registry_path))
    payload = _load_toml(registry_file)
    result = validate_invariant_registry_payload(payload, repo_root=repo_root_path)
    referenced_gates = {
        str(row.get("minimum_closeout_gate")).strip()
        for row in result.invariants
        if _non_empty_string(row.get("minimum_closeout_gate"))
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": result.status,
        "repo_root": str(repo_root_path),
        "source": {
            "registry_path": _rel(registry_file, repo_root_path),
        },
        "summary": {
            "invariant_count": len(result.invariants),
            "issue_count": len(result.issues),
            "known_minimum_closeout_gate_count": len(MINIMUM_CLOSEOUT_GATES),
            "referenced_minimum_closeout_gate_count": len(
                referenced_gates & set(MINIMUM_CLOSEOUT_GATES)
            ),
        },
        "registry_diff": {
            "unknown_scorecard_gates": sorted(
                _issue_values(result.issues, "invariant_scorecard_gate_unknown")
            ),
            "unknown_readiness_checks": sorted(
                _issue_values(result.issues, "invariant_readiness_check_unknown")
            ),
            "unknown_runtime_events": sorted(
                _issue_values(result.issues, "invariant_runtime_event_unknown")
            ),
            "unknown_minimum_closeout_gates": sorted(
                _issue_values(result.issues, "invariant_minimum_closeout_gate_unknown")
            ),
            "unregistered_minimum_closeout_gates": sorted(
                set(MINIMUM_CLOSEOUT_GATES) - referenced_gates
            ),
        },
        "catalogs": {
            "scorecard_gates": sorted(KNOWN_SCORECARD_GATES),
            "readiness_checks": sorted(KNOWN_READINESS_CHECKS),
            "runtime_events": sorted(KNOWN_RUNTIME_EVENTS),
            "minimum_closeout_gates": sorted(MINIMUM_CLOSEOUT_GATES),
        },
        "invariants": list(result.invariants),
        "issues": [issue.as_dict() for issue in result.issues],
    }


def dump_registry_report_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_registry_report_text(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    diff = payload["registry_diff"]
    lines = [
        f"{TOOL_NAME}: {payload['status']}",
        (
            "invariants={invariant_count} issues={issue_count} "
            "known_mcg={known_minimum_closeout_gate_count} "
            "referenced_mcg={referenced_minimum_closeout_gate_count}"
        ).format(**summary),
    ]
    for key in (
        "unknown_scorecard_gates",
        "unknown_readiness_checks",
        "unknown_runtime_events",
        "unknown_minimum_closeout_gates",
        "unregistered_minimum_closeout_gates",
    ):
        values = diff.get(key)
        if values:
            lines.append(f"{key}: {', '.join(str(value) for value in values)}")
    for issue in payload.get("issues", []):
        if not isinstance(issue, Mapping):
            continue
        lines.append(
            "[{severity}] {invariant_id}.{field}: {code}: {message}".format(
                severity=issue.get("severity", "error"),
                invariant_id=issue.get("invariant_id", "unknown"),
                field=issue.get("field", "unknown"),
                code=issue.get("code", "unknown"),
                message=issue.get("message", ""),
            )
        )
    return "\n".join(lines) + "\n"


def _field_shape_issues(
    row: Mapping[str, Any],
    *,
    index: int,
) -> list[InvariantRegistryIssue]:
    issues: list[InvariantRegistryIssue] = []
    label = _row_label(row, index)

    for field in sorted(REQUIRED_INVARIANT_FIELDS - set(row)):
        issues.append(
            InvariantRegistryIssue(
                code=FIELD_MISSING_CODES.get(field, "invariant_field_missing"),
                invariant_id=label,
                field=field,
                message=f"Required invariant registry field `{field}` is missing.",
            )
        )

    if "final_owner" in row:
        issues.extend(_final_owner_issues(row, index=index))

    for field in sorted(REQUIRED_STRING_INVARIANT_FIELDS - {"final_owner"}):
        if field not in row:
            continue
        if not _non_empty_string(row.get(field)):
            issues.append(
                InvariantRegistryIssue(
                    code=FIELD_MISSING_CODES.get(field, "invariant_field_invalid"),
                    invariant_id=label,
                    field=field,
                    message=f"Field `{field}` must be a non-empty string.",
                    value=row.get(field),
                )
            )

    for field in sorted(REQUIRED_LIST_INVARIANT_FIELDS):
        if field not in row:
            continue
        value = row.get(field)
        if not isinstance(value, list):
            issues.append(
                InvariantRegistryIssue(
                    code="invariant_list_field_invalid",
                    invariant_id=label,
                    field=field,
                    message=f"Field `{field}` must be a list of non-empty strings.",
                    value=value,
                )
            )
            continue
        if not value:
            issues.append(
                InvariantRegistryIssue(
                    code="invariant_list_field_empty",
                    invariant_id=label,
                    field=field,
                    message=f"Field `{field}` must contain at least one value.",
                )
            )
            continue
        if not all(_non_empty_string(item) for item in value):
            issues.append(
                InvariantRegistryIssue(
                    code="invariant_list_field_invalid",
                    invariant_id=label,
                    field=field,
                    message=f"Field `{field}` must be a list of non-empty strings.",
                    value=value,
                )
            )

    for field in sorted(OPTIONAL_LIST_INVARIANT_FIELDS):
        if field not in row:
            continue
        value = row.get(field)
        if not isinstance(value, list) or not all(_non_empty_string(item) for item in value):
            issues.append(
                InvariantRegistryIssue(
                    code="invariant_list_field_invalid",
                    invariant_id=label,
                    field=field,
                    message=f"Field `{field}` must be a list of strings.",
                    value=value,
                )
            )
    return issues


def _final_owner_issues(
    row: Mapping[str, Any],
    *,
    index: int,
) -> list[InvariantRegistryIssue]:
    label = _row_label(row, index)
    value = row.get("final_owner")
    if value is None or (isinstance(value, str) and not value.strip()):
        return [
            InvariantRegistryIssue(
                code="invariant_final_owner_missing",
                invariant_id=label,
                field="final_owner",
                message="Every invariant row must declare exactly one final_owner.",
                value=value,
            )
        ]
    if isinstance(value, list):
        if len(_string_list(value)) != 1:
            return [
                InvariantRegistryIssue(
                    code="invariant_final_owner_count_invalid",
                    invariant_id=label,
                    field="final_owner",
                    message="final_owner must contain exactly one owner.",
                    value=value,
                )
            ]
        return [
            InvariantRegistryIssue(
                code="invariant_field_invalid",
                invariant_id=label,
                field="final_owner",
                message="final_owner must be a string, not a list.",
                value=value,
            )
        ]
    if not isinstance(value, str):
        return [
            InvariantRegistryIssue(
                code="invariant_field_invalid",
                invariant_id=label,
                field="final_owner",
                message="final_owner must be a non-empty string.",
                value=value,
            )
        ]
    normalized = value.strip().casefold()
    if any(separator in normalized for separator in FINAL_OWNER_MULTI_SEPARATORS):
        return [
            InvariantRegistryIssue(
                code="invariant_final_owner_count_invalid",
                invariant_id=label,
                field="final_owner",
                message="final_owner must identify one final authority, not a compound owner list.",
                value=value,
            )
        ]
    if any(marker in normalized for marker in PROJECTION_FINAL_OWNER_MARKERS):
        return [
            InvariantRegistryIssue(
                code="invariant_final_owner_projection_not_authoritative",
                invariant_id=label,
                field="final_owner",
                message=(
                    "Projection, dashboard, bundle, and public-artifact surfaces cannot be "
                    "final closeout authority."
                ),
                value=value,
            )
        ]
    return []


def _mapping_issues(
    row: Mapping[str, Any],
    *,
    index: int,
    known_scorecard_gates: set[str] | frozenset[str],
    known_readiness_checks: set[str] | frozenset[str],
    known_runtime_events: set[str] | frozenset[str],
    minimum_closeout_gates: Mapping[str, str],
) -> list[InvariantRegistryIssue]:
    label = _row_label(row, index)
    issues: list[InvariantRegistryIssue] = []

    minimum_closeout_gate = row.get("minimum_closeout_gate")
    if _non_empty_string(minimum_closeout_gate):
        gate = str(minimum_closeout_gate).strip()
        if gate not in minimum_closeout_gates:
            issues.append(
                InvariantRegistryIssue(
                    code="invariant_minimum_closeout_gate_unknown",
                    invariant_id=label,
                    field="minimum_closeout_gate",
                    message=(
                        "minimum_closeout_gate must reference a known Minimum Closeout Gate row."
                    ),
                    value=gate,
                )
            )

    for gate_name in _field_values(row, "scorecard_gate_names", "scorecard_gates"):
        if gate_name not in known_scorecard_gates:
            issues.append(
                InvariantRegistryIssue(
                    code="invariant_scorecard_gate_unknown",
                    invariant_id=label,
                    field="scorecard_gate_names",
                    message="Scorecard gate must map to a known scorecard reader/enforcer.",
                    value=gate_name,
                )
            )

    for readiness_check in _field_values(row, "readiness_check", "readiness_checks"):
        if readiness_check not in known_readiness_checks:
            issues.append(
                InvariantRegistryIssue(
                    code="invariant_readiness_check_unknown",
                    invariant_id=label,
                    field="readiness_check",
                    message="Readiness check must map to a known readiness enforcer.",
                    value=readiness_check,
                )
            )

    for runtime_event in _field_values(
        row,
        "runtime_event_names",
        "required_runtime_events",
    ):
        if runtime_event not in known_runtime_events:
            issues.append(
                InvariantRegistryIssue(
                    code="invariant_runtime_event_unknown",
                    invariant_id=label,
                    field="runtime_event_names",
                    message="Runtime event must map to a known diagnostic event reader/enforcer.",
                    value=runtime_event,
                )
            )
    return issues


def _negative_test_ref_issues(
    row: Mapping[str, Any],
    *,
    index: int,
    repo_root: Path,
) -> list[InvariantRegistryIssue]:
    label = _row_label(row, index)
    issues: list[InvariantRegistryIssue] = []
    negative_tests = row.get("negative_tests")
    if not isinstance(negative_tests, list):
        return issues
    for raw_ref in negative_tests:
        if not _non_empty_string(raw_ref):
            continue
        ref = str(raw_ref).strip()
        path_text, separator, node = ref.partition("::")
        path = repo_root / path_text
        if separator != "::" or not node.startswith("test_") or not path.is_file():
            issues.append(
                InvariantRegistryIssue(
                    code="invariant_negative_test_ref_missing",
                    invariant_id=label,
                    field="negative_tests",
                    message=(
                        "Negative test reference must point to an existing pytest test function."
                    ),
                    value=ref,
                )
            )
            continue
        source = path.read_text(encoding="utf-8")
        if f"def {node}" not in source and f"async def {node}" not in source:
            issues.append(
                InvariantRegistryIssue(
                    code="invariant_negative_test_ref_missing",
                    invariant_id=label,
                    field="negative_tests",
                    message=(
                        "Negative test reference must point to an existing pytest test function."
                    ),
                    value=ref,
                )
            )
    return issues


def _field_values(row: Mapping[str, Any], *fields: str) -> tuple[str, ...]:
    values: list[str] = []
    for field in fields:
        raw = row.get(field)
        if _non_empty_string(raw):
            values.append(str(raw).strip())
        elif isinstance(raw, list):
            values.extend(_string_list(raw))
    return tuple(dict.fromkeys(values))


def _issue_values(
    issues: Sequence[InvariantRegistryIssue],
    code: str,
) -> set[str]:
    return {str(issue.value) for issue in issues if issue.code == code and issue.value is not None}


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _row_label(row: Mapping[str, Any], index: int) -> str:
    invariant_id = row.get("invariant_id")
    if _non_empty_string(invariant_id):
        return str(invariant_id).strip()
    return f"invariants[{index}]"


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if _non_empty_string(item)]


__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "DEFAULT_REGISTRY_RELATIVE_PATH",
    "KNOWN_READINESS_CHECKS",
    "KNOWN_RUNTIME_EVENTS",
    "KNOWN_SCORECARD_GATES",
    "MINIMUM_CLOSEOUT_GATES",
    "InvariantRegistryError",
    "InvariantRegistryIssue",
    "InvariantRegistryValidationResult",
    "ProductionInvariant",
    "ProductionInvariantRegistry",
    "build_production_invariant_registry_report",
    "dump_registry_report_json",
    "load_production_invariant_registry",
    "render_registry_report_text",
    "validate_invariant_registry_payload",
]
