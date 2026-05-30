"""Fail-closed closeout reader skeleton for Universal Policy Design Case runs."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from polisyos.runtime.quality.closeout_compatibility import (
    build_closeout_compatibility_record_from_bundle_dir,
)

CLOSEOUT_READER_SCHEMA_VERSION = "policyos.runtime.can_i_closeout.reader_skeleton.v1"
CLOSEOUT_INTEGRATION_SCHEMA_VERSION = "policyos.runtime.can_i_closeout.integration.v1"
CLOSEOUT_READER_CONTRACT_ID = "policyos.runtime.quality.closeout_reader"
CLOSEOUT_READER_CONTRACT_VERSION = "1.0.0"

_CLOSEOUT_ONLY_AUTHORITY = ("closeout_verdict",)
_CLOSEOUT_MAY_NOT_USE_FOR = (
    "approval_authority",
    "claim_authority",
    "dashboard_projection",
    "domain_evidence",
    "producer_evidence",
    "public_export",
    "readiness_authority",
    "scorecard_authority",
)
_PASS_STATUSES = frozenset({"closed", "compatible", "pass", "passed"})
_ADVISORY_STATUSES = frozenset(
    {
        "advisory",
        "degraded",
        "diagnostic",
        "diagnostic_only",
        "non_blocking",
        "nonblocking",
        "observe",
        "observe_only",
        "observed",
        "warn",
        "warning",
    }
)
_BLOCKING_STATUSES = frozenset(
    {
        "blocked",
        "cannot_closeout",
        "error",
        "fail",
        "failed",
        "hard_block",
        "invalid",
        "reissue_required",
        "review_required",
    }
)
_INCOMPLETE_STATUSES = frozenset({"incomplete", "missing", "not_ready", "pending"})
_ACCEPTED_DEFICIT_EFFECTS = frozenset({"accepted_deficit"})
_LIMITATION_EFFECTS = frozenset({"limited_closeout", "publish_with_limitation"})
_BLOCKING_CLOSEOUT_EFFECTS = frozenset(
    {"closeout_blocked", "hard_block", "reissue_required", "review_required"}
)
_ISSUE_FAIL_SEVERITIES = frozenset({"critical", "error", "fail", "failed", "hard_block"})
_ISSUE_INCOMPLETE_SEVERITIES = frozenset({"incomplete", "missing", "pending"})
_ISSUE_LIMITATION_SEVERITIES = frozenset({"limitation", "limited", "warning"})
_ISSUE_ACCEPTED_DEFICIT_SEVERITIES = frozenset({"accepted_deficit"})
_PROJECTION_ROLES = frozenset(
    {
        "diagnostic_only",
        "not_authoritative",
        "packaging_only",
        "projection_only",
    }
)
_PROJECTION_PROVENANCE = frozenset(
    {
        "bundle_overlay",
        "bundle_packaged",
        "runtime_projection",
    }
)


@dataclass(frozen=True, slots=True)
class CloseoutModuleReaderSpec:
    """One module reader slot consumed by the closeout skeleton.

    Attributes:
        module_id: Stable id for the upstream closeout input family.
        reader_contract: Runtime-quality reader contract that should own the slot.
        owner: Team that owns de-stubbing or blocker emission for the slot.
        required: Whether this reader must pass before closeout can proceed.
        stubbed: Whether W1.D only declares the reader slot without real logic.
        next_wave_target: Planned wave/phase where the reader should become real.
    """

    module_id: str
    reader_contract: str
    owner: str
    required: bool = True
    stubbed: bool = True
    next_wave_target: str = "W4.D"


DEFAULT_CLOSEOUT_MODULE_READERS: tuple[CloseoutModuleReaderSpec, ...] = (
    CloseoutModuleReaderSpec(
        module_id="formal_invariants",
        reader_contract="polisyos.runtime.quality.formal_invariants",
        owner="team-runtime-quality",
    ),
    CloseoutModuleReaderSpec(
        module_id="event_reconciliation",
        reader_contract="polisyos.runtime.quality.authority_reconciliation",
        owner="team-runtime-quality",
    ),
    CloseoutModuleReaderSpec(
        module_id="attestation",
        reader_contract="polisyos.runtime.quality.attestation",
        owner="team-runtime-quality",
    ),
    CloseoutModuleReaderSpec(
        module_id="source_truth",
        reader_contract="polisyos.runtime.quality.source_truth",
        owner="team-runtime-quality",
    ),
    CloseoutModuleReaderSpec(
        module_id="metamorphic_controls",
        reader_contract="polisyos.runtime.quality.metamorphic_controls",
        owner="team-runtime-quality",
    ),
    CloseoutModuleReaderSpec(
        module_id="performance_budget",
        reader_contract="polisyos.runtime.quality.performance_budget",
        owner="team-runtime-quality",
    ),
    CloseoutModuleReaderSpec(
        module_id="cost_degradation_telemetry",
        reader_contract="polisyos.runtime.quality.cost_degradation",
        owner="team-runtime-quality",
        required=False,
        stubbed=False,
        next_wave_target="W2.C",
    ),
    CloseoutModuleReaderSpec(
        module_id="run_cost_gate",
        reader_contract="polisyos.runtime.quality.cost_gate",
        owner="team-runtime-quality",
        required=False,
        stubbed=False,
        next_wave_target="W10.D",
    ),
    CloseoutModuleReaderSpec(
        module_id="closeout_compatibility",
        reader_contract="polisyos.runtime.quality.closeout_compatibility",
        owner="team-quality-closeout",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="rule_evolution",
        reader_contract="polisyos.runtime.quality.rule_evolution",
        owner="team-runtime-quality",
        stubbed=False,
        next_wave_target="W2.B",
    ),
    CloseoutModuleReaderSpec(
        module_id="semantic_binding",
        reader_contract="polisyos.runtime.quality.semantic_binding",
        owner="team-runtime-quality",
    ),
    CloseoutModuleReaderSpec(
        module_id="claim_registry",
        reader_contract="polisyos.runtime.quality.claim_registry",
        owner="team-scientist-evidence",
    ),
    CloseoutModuleReaderSpec(
        module_id="pdc_record_family_status",
        reader_contract="polisyos.runtime.quality.policy_design_case",
        owner="team-policyos-runtime",
    ),
    CloseoutModuleReaderSpec(
        module_id="projection_publication_state",
        reader_contract="polisyos.runtime.quality.projection_semantics",
        owner="team-policyos-runtime",
    ),
    CloseoutModuleReaderSpec(
        module_id="complexity_self_fmea",
        reader_contract="polisyos.runtime.quality.run_cost_proportionality",
        owner="team-runtime-quality",
    ),
)

DEFAULT_CLOSEOUT_INTEGRATION_MODULE_READERS: tuple[CloseoutModuleReaderSpec, ...] = (
    CloseoutModuleReaderSpec(
        module_id="i4_policy_design_case_graph",
        reader_contract="polisyos.runtime.quality.policy_design_case#wave4_i4_graph",
        owner="team-policyos-runtime",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="portfolio_effective_support",
        reader_contract="polisyos.runtime.quality.evidence_independence",
        owner="team-science-quality",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="lifecycle_reissue",
        reader_contract="polisyos.runtime.quality.case_lifecycle",
        owner="team-policyos-runtime",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="projection_consumer_contract",
        reader_contract="polisyos.runtime.quality.projection_semantics#consumer_contract",
        owner="team-policyos-runtime",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="formal_invariants",
        reader_contract="polisyos.runtime.quality.formal_invariants",
        owner="team-runtime-quality",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="source_truth",
        reader_contract="polisyos.runtime.quality.source_truth",
        owner="team-runtime-quality",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="conflict_materialization",
        reader_contract="polisyos.scientist.cross_graph.conflict_materializer#w8e",
        owner="team-scientist-evidence",
        stubbed=False,
        next_wave_target="W8.E",
    ),
    CloseoutModuleReaderSpec(
        module_id="attestation",
        reader_contract="polisyos.runtime.quality.attestation",
        owner="team-runtime-quality",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="closeout_compatibility",
        reader_contract="polisyos.runtime.quality.closeout_compatibility",
        owner="team-quality-closeout",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="semantic_binding",
        reader_contract="polisyos.runtime.quality.semantic_binding",
        owner="team-runtime-quality",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="claim_registry",
        reader_contract="polisyos.runtime.quality.claim_registry",
        owner="team-scientist-evidence",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="pdc_record_family_status",
        reader_contract="polisyos.runtime.quality.policy_design_case",
        owner="team-policyos-runtime",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="projection_publication_state",
        reader_contract="polisyos.runtime.quality.projection_semantics",
        owner="team-policyos-runtime",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="run_cost_gate",
        reader_contract="polisyos.runtime.quality.cost_gate",
        owner="team-runtime-quality",
        required=False,
        stubbed=False,
        next_wave_target="W10.D",
    ),
    CloseoutModuleReaderSpec(
        module_id="complexity_self_fmea",
        reader_contract="polisyos.runtime.quality.run_cost_proportionality",
        owner="team-runtime-quality",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="audit_verifier_ingestion",
        reader_contract="polisyos.core.audit.verifier",
        owner="team-core-audit",
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="deficit_crosswalk",
        reader_contract="polisyos.runtime.quality.status_deficits",
        owner="team-runtime-quality",
        required=False,
        stubbed=False,
    ),
    CloseoutModuleReaderSpec(
        module_id="prompt_tool_repair_fmea",
        reader_contract="polisyos.runtime.quality.prompt_tool_ledger#repair_fmea",
        owner="team-runtime-ops",
        required=False,
        stubbed=False,
        next_wave_target="W10.F",
    ),
)

CLOSEOUT_INTEGRATION_REPORT_FILES = {
    "i4_policy_design_case_graph": ("policy_design_case_i4_graph.json",),
    "portfolio_effective_support": (
        "policy_design_portfolio_effective_support.json",
        "evidence_independence_map.json",
    ),
    "lifecycle_reissue": ("lifecycle_reissue_report.json", "claim_lifecycle_reissue.json"),
    "projection_consumer_contract": (
        "policy_design_case_projection_contract_fixture.json",
        "projection_contract_fixture.json",
    ),
    "formal_invariants": ("formal_invariants.json",),
    "source_truth": ("source_truth.json", "source_truth_conflicts.json"),
    "conflict_materialization": (
        "conflict_materialization_closeout.json",
        "conflict_materialization.json",
        "policy_conflict_materialization.json",
    ),
    "attestation": ("attestation.json", "trust_boundary_attestation.json"),
    "closeout_compatibility": ("can_i_closeout_compatibility.json",),
    "semantic_binding": ("semantic_binding_ledger.json", "semantic_binding.json"),
    "claim_registry": ("claim_registry.json", "runtime_claim_registry.json"),
    "pdc_record_family_status": ("policy_design_case.json",),
    "projection_publication_state": (
        "projection_publication_state.json",
        "policy_design_case_projection.json",
        "typed_projection.json",
    ),
    "run_cost_gate": ("run_cost_gate.json",),
    "complexity_self_fmea": (
        "run_cost_proportionality.json",
        "complexity_self_fmea.json",
    ),
    "audit_verifier_ingestion": ("audit_verifier.json", "audit_verifier_ingestion.json"),
    "deficit_crosswalk": ("status_envelope.json", "deficit_crosswalk.json"),
    "prompt_tool_repair_fmea": ("prompt_tool_repair_fmea.json", "prompt_tool_ledger.json"),
}


def build_closeout_reader_skeleton(
    *,
    run_id: str | None = None,
    module_records: Mapping[str, Mapping[str, Any]] | None = None,
    substitute_records: Sequence[Mapping[str, Any]] | None = None,
    module_readers: Sequence[CloseoutModuleReaderSpec] = DEFAULT_CLOSEOUT_MODULE_READERS,
    compatibility_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the W1.D closeout reader verdict without minting domain authority.

    Args:
        run_id: Runtime run identifier carried for inspection.
        module_records: Optional module-owned evidence records keyed by module id.
        substitute_records: Dashboard, readiness, package, or public-export
            surfaces that attempted to stand in for closeout evidence.
        module_readers: Reader slots to evaluate. The default includes the
            W1.D stubs plus the existing closeout compatibility reader.
        compatibility_record: Existing compatibility record to wire into the
            `closeout_compatibility` reader slot.

    Returns:
        A typed, fail-closed closeout reader skeleton verdict.
    """

    records = {str(key): dict(value) for key, value in (module_records or {}).items()}
    if compatibility_record is not None:
        records.setdefault("closeout_compatibility", dict(compatibility_record))

    module_results: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for spec in module_readers:
        result = _read_module_stub(spec=spec, record=records.get(spec.module_id))
        module_results.append(result)
        issues.extend(result["issues"])

    substitution_rejections = [
        rejection
        for index, record in enumerate(substitute_records or ())
        if (rejection := _substitution_rejection(record, index=index)) is not None
    ]
    issues.extend(substitution_rejections)

    has_fail = any(issue.get("severity") == "fail" for issue in issues)
    has_incomplete = any(issue.get("severity") == "incomplete" for issue in issues)
    status = "blocked" if has_fail else "incomplete" if has_incomplete else "closed"
    return {
        "schema_version": CLOSEOUT_READER_SCHEMA_VERSION,
        "contract_id": CLOSEOUT_READER_CONTRACT_ID,
        "contract_version": CLOSEOUT_READER_CONTRACT_VERSION,
        "status": status,
        "verdict": "can_closeout" if status == "closed" else "cannot_closeout",
        "can_closeout": status == "closed",
        "run_id": _text(run_id),
        "capability_reality_state": (
            "implemented" if status == "closed" else "implemented_but_not_orchestrated"
        ),
        "authority_envelope": _closeout_authority_envelope(run_id=run_id),
        "summary": {
            "module_reader_count": len(module_results),
            "passing_module_count": sum(1 for row in module_results if row["status"] == "pass"),
            "stubbed_module_count": sum(1 for row in module_results if row["status"] == "stubbed"),
            "missing_module_count": sum(1 for row in module_results if row["status"] == "missing"),
            "failed_module_count": sum(1 for row in module_results if row["status"] == "fail"),
            "substitution_rejection_count": len(substitution_rejections),
            "issue_count": len(issues),
        },
        "module_reader_results": module_results,
        "substitution_rejections": substitution_rejections,
        "issues": issues,
    }


def build_closeout_reader_skeleton_from_bundle_dir(
    bundle_dir: Path,
    *,
    run_id: str | None = None,
    substitute_records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the closeout reader skeleton from an evidence bundle directory.

    Args:
        bundle_dir: Evidence bundle directory containing `bundle.json` and
            `quality_evidence/` files.
        run_id: Runtime run identifier carried for inspection.
        substitute_records: Optional projection/readiness/package surfaces that
            attempted to stand in for closeout evidence.

    Returns:
        A fail-closed reader skeleton verdict with the compatibility record
        attached for inspection.
    """

    compatibility = build_closeout_compatibility_record_from_bundle_dir(bundle_dir)
    record = build_closeout_reader_skeleton(
        run_id=run_id,
        compatibility_record=compatibility,
        substitute_records=substitute_records,
    )
    record["compatibility_record"] = compatibility
    record["bundle_dir"] = str(bundle_dir)
    return record


def build_can_i_closeout_verdict(
    *,
    run_id: str | None = None,
    module_records: Mapping[str, Mapping[str, Any]] | None = None,
    module_readers: Sequence[
        CloseoutModuleReaderSpec
    ] = DEFAULT_CLOSEOUT_INTEGRATION_MODULE_READERS,
    compatibility_record: Mapping[str, Any] | None = None,
    readiness_record: Mapping[str, Any] | None = None,
    scorecard_record: Mapping[str, Any] | None = None,
    projection_record: Mapping[str, Any] | None = None,
    audit_verifier_record: Mapping[str, Any] | None = None,
    substitute_records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the W4.D Can-I-Closeout verdict over real upstream records.

    Args:
        run_id: Runtime run identifier carried for inspection.
        module_records: Module-owned closeout records keyed by W4 module id.
        module_readers: Reader slots to evaluate. The default W4 set has no
            stubs; missing required records become integration blockers.
        compatibility_record: Optional compatibility record, normally emitted
            by `closeout_compatibility`.
        readiness_record: Optional readiness surface. Its failures are ingested
            as blockers, but its pass state is observed only.
        scorecard_record: Optional scorecard surface. Its blockers are ingested,
            but a passing scorecard cannot satisfy closeout.
        projection_record: Optional typed projection-state verification record.
            Raw projection-only authority is rejected by the module reader.
        audit_verifier_record: Optional audit-verifier ingestion record.
        substitute_records: Dashboard, readiness, package, or public-export
            surfaces that attempted to stand in for closeout evidence.

    Returns:
        A closeout-only verdict with preserved upstream blocker, limitation,
        and accepted-deficit provenance.
    """

    records = {str(key): dict(value) for key, value in (module_records or {}).items()}
    if compatibility_record is not None:
        records.setdefault("closeout_compatibility", dict(compatibility_record))
    if projection_record is not None:
        records.setdefault("projection_publication_state", dict(projection_record))
    if audit_verifier_record is not None:
        records.setdefault("audit_verifier_ingestion", dict(audit_verifier_record))

    module_results: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    limitations: list[dict[str, Any]] = []
    accepted_deficits: list[dict[str, Any]] = []
    for spec in module_readers:
        result = _read_closeout_module(spec=spec, record=records.get(spec.module_id))
        module_results.append(result)
        issues.extend(result["issues"])
        blockers.extend(result["blockers"])
        limitations.extend(result["limitations"])
        accepted_deficits.extend(result["accepted_deficits"])

    observed_surfaces: list[dict[str, Any]] = []
    for surface, record in (
        ("readiness", readiness_record),
        ("scorecard", scorecard_record),
    ):
        if record is None:
            continue
        observation, surface_blockers = _surface_observation(surface, record)
        observed_surfaces.append(observation)
        blockers.extend(surface_blockers)
        issues.extend(_surface_issues(surface_blockers))

    substitution_rejections = [
        rejection
        for index, record in enumerate(substitute_records or ())
        if (rejection := _substitution_rejection(record, index=index)) is not None
    ]
    issues.extend(substitution_rejections)
    blockers.extend(
        _blocker_from_issue(
            issue,
            source_module_id="substitute_surface",
            source_reader_contract=CLOSEOUT_READER_CONTRACT_ID,
            source_status=None,
        )
        for issue in substitution_rejections
    )

    has_fail = any(issue.get("severity") == "fail" for issue in issues)
    has_incomplete = any(issue.get("severity") == "incomplete" for issue in issues)
    if has_fail:
        status = "blocked"
    elif has_incomplete:
        status = "incomplete"
    elif limitations:
        status = "closed_with_limitations"
    elif accepted_deficits:
        status = "closed_with_accepted_deficits"
    else:
        status = "closed"
    can_closeout = status in {
        "closed",
        "closed_with_accepted_deficits",
        "closed_with_limitations",
    }
    return {
        "schema_version": CLOSEOUT_INTEGRATION_SCHEMA_VERSION,
        "contract_id": CLOSEOUT_READER_CONTRACT_ID,
        "contract_version": CLOSEOUT_READER_CONTRACT_VERSION,
        "status": status,
        "verdict": _integration_verdict(status),
        "can_closeout": can_closeout,
        "closeout_effect": _integration_closeout_effect(
            status=status,
            accepted_deficits=accepted_deficits,
            limitations=limitations,
        ),
        "run_id": _text(run_id),
        "integration_slice": "I4",
        "capability_reality_state": (
            "bridge_missing" if status == "incomplete" else "implemented"
        ),
        "authority_envelope": _closeout_authority_envelope(run_id=run_id),
        "summary": {
            "module_reader_count": len(module_results),
            "passing_module_count": sum(1 for row in module_results if row["status"] == "pass"),
            "optional_missing_module_count": sum(
                1 for row in module_results if row["status"] == "optional_missing"
            ),
            "missing_module_count": sum(1 for row in module_results if row["status"] == "missing"),
            "failed_module_count": sum(1 for row in module_results if row["status"] == "fail"),
            "observed_surface_count": len(observed_surfaces),
            "substitution_rejection_count": len(substitution_rejections),
            "blocker_count": len(blockers),
            "limitation_count": len(limitations),
            "accepted_deficit_count": len(accepted_deficits),
            "issue_count": len(issues),
        },
        "module_reader_results": module_results,
        "observed_surfaces": observed_surfaces,
        "substitution_rejections": substitution_rejections,
        "blockers": blockers,
        "limitations": limitations,
        "accepted_deficits": accepted_deficits,
        "issues": issues,
    }


def build_can_i_closeout_verdict_from_bundle_dir(
    bundle_dir: Path,
    *,
    run_id: str | None = None,
    substitute_records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the W4.D closeout integration verdict from a bundle directory."""

    compatibility = build_closeout_compatibility_record_from_bundle_dir(bundle_dir)
    quality_dir = bundle_dir.resolve() / "quality_evidence"
    records = _integration_records_from_quality_dir(quality_dir)
    records.setdefault("closeout_compatibility", compatibility)
    verdict = build_can_i_closeout_verdict(
        run_id=run_id,
        module_records=records,
        readiness_record=_load_json_or_none(quality_dir / "readiness.json"),
        scorecard_record=_load_json_or_none(quality_dir / "quality_scorecard.json"),
        substitute_records=substitute_records,
    )
    verdict["compatibility_record"] = compatibility
    verdict["bundle_dir"] = str(bundle_dir)
    return verdict


def _read_module_stub(
    *,
    spec: CloseoutModuleReaderSpec,
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if record is None:
        if not spec.required:
            return _module_result(spec, "optional_missing", record, [])
        issues = [
            _issue(
                "closeout_module_evidence_missing",
                (
                    f"Closeout module {spec.module_id} has no reader evidence. "
                    "The W1.D skeleton fails closed until the module is wired."
                ),
                severity="incomplete",
                module_id=spec.module_id,
                owner=spec.owner,
                next_action=(
                    f"Wire {spec.module_id} into the closeout reader in "
                    f"{spec.next_wave_target} or emit an explicit typed blocker."
                ),
            )
        ]
        if spec.stubbed:
            issues.append(
                _issue(
                    "closeout_module_reader_stubbed",
                    (
                        f"Closeout module {spec.module_id} is declared but still "
                        "stubbed in W1.D. A missing stub cannot satisfy closeout."
                    ),
                    severity="incomplete",
                    module_id=spec.module_id,
                    owner=spec.owner,
                    next_action=(
                        f"Implement the {spec.module_id} reader before this slot "
                        f"can close out in {spec.next_wave_target}."
                    ),
                )
            )
        return _module_result(spec, "missing", record, issues)

    status = _status(record)
    if not spec.required and status in _ADVISORY_STATUSES:
        return _module_result(spec, status or "advisory", record, [])

    authority_issue_code = _module_authority_rejection_code(record)
    if authority_issue_code is not None:
        issue = _issue(
            authority_issue_code,
            (
                f"Closeout module {spec.module_id} supplied projection, packaging, "
                "or non-authoritative evidence."
            ),
            module_id=spec.module_id,
            owner=spec.owner,
            next_action=(
                "Replace projection/package/readiness material with module-owned "
                "runtime evidence or a typed closeout blocker."
            ),
        )
        return _module_result(spec, "fail", record, [issue])

    if spec.stubbed:
        issue = _issue(
            "closeout_module_reader_stubbed",
            (
                f"Closeout module {spec.module_id} is declared but still stubbed in W1.D. "
                "A stub cannot satisfy closeout."
            ),
            severity="incomplete",
            module_id=spec.module_id,
            owner=spec.owner,
            next_action=(
                f"Implement the {spec.module_id} reader before this slot can close "
                f"out in {spec.next_wave_target}."
            ),
        )
        return _module_result(spec, "stubbed", record, [issue])

    if status in _PASS_STATUSES:
        return _module_result(spec, "pass", record, [])

    issue = _issue(
        "closeout_module_evidence_failed",
        f"Closeout module {spec.module_id} did not pass its reader check.",
        module_id=spec.module_id,
        owner=spec.owner,
        next_action=(
            "Resolve the module-owned blocker before using the closeout reader "
            "verdict for release decisions."
        ),
        source_status=status or "missing",
        child_issue_codes=_child_issue_codes(record),
    )
    return _module_result(spec, "fail", record, [issue])


def _read_closeout_module(
    *,
    spec: CloseoutModuleReaderSpec,
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if record is None:
        if not spec.required:
            return _integration_module_result(spec, "optional_missing", record, [], [], [], [])
        issue = _issue(
            "closeout_module_evidence_missing",
            (
                f"Closeout module {spec.module_id} has no W4.D reader evidence. "
                "A local readiness or scorecard pass cannot substitute for this record."
            ),
            severity="incomplete",
            module_id=spec.module_id,
            owner=spec.owner,
            next_action=(
                f"Emit the {spec.module_id} closeout reader record or a typed "
                f"integration blocker for {spec.next_wave_target}."
            ),
        )
        return _integration_module_result(spec, "missing", record, [issue], [], [], [])

    status = _status(record)
    authority_issue_code = _module_authority_rejection_code(record)
    if authority_issue_code is not None:
        issue = _issue(
            authority_issue_code,
            (
                f"Closeout module {spec.module_id} supplied projection, packaging, "
                "or non-authoritative evidence."
            ),
            module_id=spec.module_id,
            owner=spec.owner,
            next_action=(
                "Replace projection/package/readiness material with module-owned "
                "runtime evidence or a typed closeout blocker."
            ),
        )
        blocker = _blocker_from_issue(
            issue,
            source_module_id=spec.module_id,
            source_reader_contract=spec.reader_contract,
            source_status=status,
            record=record,
        )
        return _integration_module_result(spec, "fail", record, [issue], [blocker], [], [])

    record_issues, record_blockers, limitations, accepted_deficits = (
        _classify_record_closeout_items(spec=spec, record=record)
    )
    if spec.stubbed:
        issue = _issue(
            "closeout_module_reader_stubbed",
            (
                f"Closeout module {spec.module_id} is still stubbed. "
                "W4.D cannot close out over pre-I4 stubs."
            ),
            severity="incomplete",
            module_id=spec.module_id,
            owner=spec.owner,
            next_action=(
                f"Implement the {spec.module_id} reader before this slot can close "
                f"out in {spec.next_wave_target}."
            ),
        )
        return _integration_module_result(
            spec,
            "stubbed",
            record,
            [*record_issues, issue],
            record_blockers,
            limitations,
            accepted_deficits,
        )

    if record_blockers:
        return _integration_module_result(
            spec,
            "fail",
            record,
            record_issues,
            record_blockers,
            limitations,
            accepted_deficits,
        )
    if status in _PASS_STATUSES or (not spec.required and status in _ADVISORY_STATUSES):
        return _integration_module_result(
            spec,
            "pass" if status in _PASS_STATUSES else status or "observe",
            record,
            record_issues,
            [],
            limitations,
            accepted_deficits,
        )
    if status in _INCOMPLETE_STATUSES:
        issue = _issue(
            "closeout_module_evidence_incomplete",
            f"Closeout module {spec.module_id} emitted incomplete reader evidence.",
            severity="incomplete",
            module_id=spec.module_id,
            owner=spec.owner,
            next_action="Complete the module-owned reader evidence before closeout.",
            source_status=status or "missing",
            child_issue_codes=_child_issue_codes(record),
        )
        return _integration_module_result(
            spec,
            "missing",
            record,
            [*record_issues, issue],
            [],
            limitations,
            accepted_deficits,
        )

    issue = _issue(
        "closeout_module_evidence_failed",
        f"Closeout module {spec.module_id} did not pass its reader check.",
        module_id=spec.module_id,
        owner=spec.owner,
        next_action=(
            "Resolve the module-owned blocker before using the closeout reader "
            "verdict for release decisions."
        ),
        source_status=status or "missing",
        child_issue_codes=_child_issue_codes(record),
    )
    blocker = _blocker_from_issue(
        issue,
        source_module_id=spec.module_id,
        source_reader_contract=spec.reader_contract,
        source_status=status,
        record=record,
    )
    return _integration_module_result(
        spec,
        "fail",
        record,
        [*record_issues, issue],
        [*record_blockers, blocker],
        limitations,
        accepted_deficits,
    )


def _module_result(
    spec: CloseoutModuleReaderSpec,
    status: str,
    record: Mapping[str, Any] | None,
    issues: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "module_id": spec.module_id,
        "reader_contract": spec.reader_contract,
        "owner": spec.owner,
        "required": spec.required,
        "stubbed": spec.stubbed,
        "status": status,
        "blocking": spec.required and status != "pass",
        "source_schema_version": _text(record.get("schema_version")) if record else None,
        "source_status": _status(record or {}),
        "authority_role": _text((record or {}).get("authority_role")),
        "provenance_kind": _text((record or {}).get("provenance_kind")),
        "issue_codes": [str(issue["code"]) for issue in issues],
        "issues": [dict(issue) for issue in issues],
    }


def _integration_module_result(
    spec: CloseoutModuleReaderSpec,
    status: str,
    record: Mapping[str, Any] | None,
    issues: Sequence[Mapping[str, Any]],
    blockers: Sequence[Mapping[str, Any]],
    limitations: Sequence[Mapping[str, Any]],
    accepted_deficits: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    result = _module_result(spec, status, record, issues)
    result["blocking"] = spec.required and status not in {"pass", "observe", "observed"}
    result["blocker_count"] = len(blockers)
    result["limitation_count"] = len(limitations)
    result["accepted_deficit_count"] = len(accepted_deficits)
    result["blockers"] = [dict(item) for item in blockers]
    result["limitations"] = [dict(item) for item in limitations]
    result["accepted_deficits"] = [dict(item) for item in accepted_deficits]
    return result


def _classify_record_closeout_items(
    *,
    spec: CloseoutModuleReaderSpec,
    record: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    limitations: list[dict[str, Any]] = []
    accepted_deficits: list[dict[str, Any]] = []

    status = _status(record)
    has_upstream_fail_issue = any(
        isinstance(raw_issue, Mapping)
        and ((_text(raw_issue.get("severity")) or "").casefold() in _ISSUE_FAIL_SEVERITIES)
        for raw_issue in record.get("issues") or ()
    )
    if status in _BLOCKING_STATUSES and not has_upstream_fail_issue:
        issue = _issue(
            "closeout_module_evidence_failed",
            f"Closeout module {spec.module_id} emitted blocking status {status}.",
            module_id=spec.module_id,
            owner=spec.owner,
            next_action="Resolve the upstream blocking status before closeout.",
            source_status=status,
            child_issue_codes=_child_issue_codes(record),
        )
        issues.append(issue)
        blockers.append(
            _blocker_from_issue(
                issue,
                source_module_id=spec.module_id,
                source_reader_contract=spec.reader_contract,
                source_status=status,
                record=record,
            )
        )

    for raw_issue in record.get("issues") or ():
        if not isinstance(raw_issue, Mapping):
            continue
        severity = (_text(raw_issue.get("severity")) or "").casefold()
        if severity in _ISSUE_FAIL_SEVERITIES:
            issue = _issue_from_upstream(raw_issue, spec=spec, record=record, severity="fail")
            issues.append(issue)
            blockers.append(
                _blocker_from_issue(
                    issue,
                    source_module_id=spec.module_id,
                    source_reader_contract=spec.reader_contract,
                    source_status=status,
                    record=record,
                    upstream_issue=raw_issue,
                )
            )
        elif severity in _ISSUE_INCOMPLETE_SEVERITIES:
            issues.append(
                _issue_from_upstream(raw_issue, spec=spec, record=record, severity="incomplete")
            )
        elif severity in _ISSUE_ACCEPTED_DEFICIT_SEVERITIES:
            accepted_deficits.append(
                _accepted_deficit_from_issue(raw_issue, spec=spec, record=record)
            )
        elif severity in _ISSUE_LIMITATION_SEVERITIES:
            limitations.append(_limitation_from_issue(raw_issue, spec=spec, record=record))

    for row in _deficit_rows(record):
        effect = (_text(row.get("closeout_effect")) or "").casefold()
        disposition = (_text(row.get("disposition")) or "").casefold()
        if effect in _ACCEPTED_DEFICIT_EFFECTS or disposition == "accepted_deficit":
            accepted_deficits.append(_accepted_deficit_from_row(row, spec=spec, record=record))
        elif effect in _LIMITATION_EFFECTS or disposition == "publish_with_limitation":
            limitations.append(_limitation_from_row(row, spec=spec, record=record))
        elif effect in _BLOCKING_CLOSEOUT_EFFECTS:
            issue = _issue(
                _closeout_effect_issue_code(effect),
                "Deficit crosswalk blocks closeout for the affected authority scope.",
                module_id=spec.module_id,
                owner=spec.owner,
                next_action=_text(row.get("next_action"))
                or "Resolve, reissue, or review the deficit before closeout.",
                source_status=status,
                deficit_id=_text(row.get("deficit_id")),
                closeout_effect=effect,
                claim_id=_first_text(row.get("claim_ids")),
            )
            issues.append(issue)
            blockers.append(
                _blocker_from_issue(
                    issue,
                    source_module_id=spec.module_id,
                    source_reader_contract=spec.reader_contract,
                    source_status=status,
                    record=record,
                    upstream_issue=row,
                )
            )
    return issues, blockers, limitations, accepted_deficits


def _deficit_rows(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw_rows = record.get("deficit_crosswalk")
    if isinstance(raw_rows, Sequence) and not isinstance(raw_rows, str | bytes):
        return [row for row in raw_rows if isinstance(row, Mapping)]
    if isinstance(raw_rows, Mapping):
        return [row for row in raw_rows.values() if isinstance(row, Mapping)]
    return []


def _issue_from_upstream(
    issue: Mapping[str, Any],
    *,
    spec: CloseoutModuleReaderSpec,
    record: Mapping[str, Any],
    severity: str,
) -> dict[str, Any]:
    upstream_code = _text(issue.get("code")) or "upstream_closeout_issue"
    return _issue(
        "closeout_upstream_reader_issue",
        _text(issue.get("message")) or f"Upstream closeout issue {upstream_code}.",
        severity=severity,
        module_id=spec.module_id,
        owner=spec.owner,
        next_action=_text(issue.get("next_action"))
        or "Resolve the upstream reader issue before closeout.",
        upstream_issue_code=upstream_code,
        source_status=_status(record),
        claim_id=_text(issue.get("claim_id")),
    )


def _blocker_from_issue(
    issue: Mapping[str, Any],
    *,
    source_module_id: str,
    source_reader_contract: str,
    source_status: str | None,
    record: Mapping[str, Any] | None = None,
    upstream_issue: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    upstream = upstream_issue or issue
    return {
        "code": _text(issue.get("code")) or "closeout_blocker",
        "upstream_issue_code": _text(upstream.get("code")) or _text(issue.get("code")),
        "message": _text(issue.get("message")) or "Closeout blocker.",
        "source_module_id": source_module_id,
        "source_reader_contract": source_reader_contract,
        "source_status": source_status,
        "source_schema_version": _text((record or {}).get("schema_version")),
        "source_producer": _source_producer(upstream, record),
        "claim_id": _text(upstream.get("claim_id")) or _text(issue.get("claim_id")),
        "deficit_id": _text(upstream.get("deficit_id")) or _text(issue.get("deficit_id")),
        "next_action": _text(issue.get("next_action")),
    }


def _limitation_from_issue(
    issue: Mapping[str, Any],
    *,
    spec: CloseoutModuleReaderSpec,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    return _limitation_payload(
        spec=spec,
        record=record,
        source=issue,
        limitation_id=_text(issue.get("limitation_id") or issue.get("code")),
        message=_text(issue.get("message")),
    )


def _limitation_from_row(
    row: Mapping[str, Any],
    *,
    spec: CloseoutModuleReaderSpec,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    return _limitation_payload(
        spec=spec,
        record=record,
        source=row,
        limitation_id=_text(row.get("deficit_id") or row.get("deficit_code")),
        message=_text(row.get("public_limitation_note") or row.get("message")),
    )


def _limitation_payload(
    *,
    spec: CloseoutModuleReaderSpec,
    record: Mapping[str, Any],
    source: Mapping[str, Any],
    limitation_id: str | None,
    message: str | None,
) -> dict[str, Any]:
    payload = _provenance_payload(spec=spec, record=record, source=source)
    payload.update(
        {
            "limitation_id": limitation_id,
            "deficit_id": _text(source.get("deficit_id")),
            "message": message or "Closeout may proceed only with this limitation.",
            "closeout_effect": _text(source.get("closeout_effect")) or "limited_closeout",
        }
    )
    return payload


def _accepted_deficit_from_issue(
    issue: Mapping[str, Any],
    *,
    spec: CloseoutModuleReaderSpec,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    return _accepted_deficit_payload(
        spec=spec,
        record=record,
        source=issue,
        deficit_id=_text(issue.get("deficit_id") or issue.get("code")),
        message=_text(issue.get("message")),
    )


def _accepted_deficit_from_row(
    row: Mapping[str, Any],
    *,
    spec: CloseoutModuleReaderSpec,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    return _accepted_deficit_payload(
        spec=spec,
        record=record,
        source=row,
        deficit_id=_text(row.get("deficit_id") or row.get("deficit_code")),
        message=_text(row.get("public_limitation_note") or row.get("message")),
    )


def _accepted_deficit_payload(
    *,
    spec: CloseoutModuleReaderSpec,
    record: Mapping[str, Any],
    source: Mapping[str, Any],
    deficit_id: str | None,
    message: str | None,
) -> dict[str, Any]:
    payload = _provenance_payload(spec=spec, record=record, source=source)
    payload.update(
        {
            "deficit_id": deficit_id,
            "message": message or "Accepted deficit preserved for closeout.",
            "closeout_effect": "accepted_deficit",
        }
    )
    return payload


def _provenance_payload(
    *,
    spec: CloseoutModuleReaderSpec,
    record: Mapping[str, Any],
    source: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source_module_id": spec.module_id,
        "source_reader_contract": spec.reader_contract,
        "source_status": _status(record),
        "source_schema_version": _text(record.get("schema_version")),
        "source_producer": _source_producer(source, record),
        "claim_id": _text(source.get("claim_id")) or _first_text(source.get("claim_ids")),
        "authority_level": _text(source.get("authority_level")),
        "audience_scope": _text(source.get("audience_scope")),
        "owner": _text(source.get("owner")) or spec.owner,
        "evidence_ref": _text(source.get("evidence_ref")) or _text(record.get("cas_ref")),
        "runtime_event_ref": _text(source.get("runtime_event_ref"))
        or _text(record.get("runtime_event_ref")),
    }


def _substitution_rejection(
    record: Mapping[str, Any],
    *,
    index: int,
) -> dict[str, Any] | None:
    code = _substitution_rejection_code(record)
    if code is None:
        return None
    surface = _surface(record) or f"substitute_{index}"
    return _issue(
        code,
        (
            f"{surface} is not closeout evidence. Readiness, dashboard, packaging, "
            "and public export surfaces cannot substitute for closeout substrate readers."
        ),
        surface=surface,
        authority_role=_text(record.get("authority_role")),
        provenance_kind=_text(record.get("provenance_kind")),
        next_action=(
            "Use the surface only for display or routing, and provide module-owned "
            "runtime evidence to the closeout reader."
        ),
    )


def _substitution_rejection_code(record: Mapping[str, Any]) -> str | None:
    surface = (_surface(record) or "").casefold()
    role = (_text(record.get("authority_role")) or "").casefold()
    provenance = (_text(record.get("provenance_kind")) or "").casefold()
    if surface in {"readiness", "readiness_summary"} or role == "readiness_input":
        return "closeout_readiness_not_closeout_evidence"
    if surface in {"dashboard", "dashboard_projection", "api_projection"}:
        return "closeout_dashboard_projection_not_authority"
    if surface in {"public_export", "public-export", "public"}:
        return "closeout_public_export_not_authority"
    if surface in {"bundle", "package", "packaging"} or role == "packaging_only":
        return "closeout_packaging_not_authority"
    if role in _PROJECTION_ROLES or provenance in _PROJECTION_PROVENANCE:
        return "closeout_projection_only_not_authority"
    if "runtime_closeout_authority" in _forbidden_uses(record):
        return "closeout_projection_only_not_authority"
    return None


def _module_authority_rejection_code(record: Mapping[str, Any]) -> str | None:
    role = (_text(record.get("authority_role")) or "").casefold()
    provenance = (_text(record.get("provenance_kind")) or "").casefold()
    if role in _PROJECTION_ROLES or provenance in _PROJECTION_PROVENANCE:
        return "closeout_projection_only_not_authority"
    if "runtime_closeout_authority" in _forbidden_uses(record):
        return "closeout_projection_only_not_authority"
    return None


def _surface_observation(
    surface: str,
    record: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    blockers = _surface_blockers(surface, record)
    return (
        {
            "surface": surface,
            "status": _status(record),
            "closeout_authority_effect": "observed_only",
            "blocker_count": len(blockers),
            "source_schema_version": _text(record.get("schema_version")),
        },
        blockers,
    )


def _surface_blockers(surface: str, record: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    status = _status(record)
    if status in _BLOCKING_STATUSES:
        blockers.append(
            {
                "code": f"closeout_{surface}_observed_blocker",
                "upstream_issue_code": f"{surface}_{status}",
                "message": f"{surface} reported blocking status {status}.",
                "source_module_id": f"{surface}_surface",
                "source_reader_contract": f"polisyos.runtime.quality.{surface}",
                "source_status": status,
                "source_schema_version": _text(record.get("schema_version")),
                "source_producer": _source_producer(record, record),
                "next_action": (
                    f"Resolve the {surface} blocker and rerun closeout integration."
                ),
            }
        )
    for key in ("blocking_quality_failures", "failures", "blockers"):
        for failure in _mapping_rows(record.get(key)):
            blockers.append(
                {
                    "code": f"closeout_{surface}_observed_blocker",
                    "upstream_issue_code": _text(failure.get("code"))
                    or f"{surface}_blocking_failure",
                    "message": _text(failure.get("message"))
                    or f"{surface} reported a blocking failure.",
                    "source_module_id": f"{surface}_surface",
                    "source_reader_contract": f"polisyos.runtime.quality.{surface}",
                    "source_status": status,
                    "source_schema_version": _text(record.get("schema_version")),
                    "source_producer": _source_producer(failure, record),
                    "claim_id": _text(failure.get("claim_id")),
                    "next_action": _text(failure.get("next_action"))
                    or f"Resolve the {surface} failure before closeout.",
                }
            )
    for gate in _mapping_rows(record.get("quality_gates")):
        if bool(gate.get("blocking")) and (_status(gate) in _BLOCKING_STATUSES):
            blockers.append(
                {
                    "code": "closeout_scorecard_gate_blocker",
                    "upstream_issue_code": _text(gate.get("code") or gate.get("name"))
                    or "scorecard_gate_blocker",
                    "message": _text(gate.get("message"))
                    or "Scorecard gate reported a closeout blocker.",
                    "source_module_id": "scorecard_surface",
                    "source_reader_contract": "polisyos.runtime.quality.scorecard",
                    "source_status": _status(gate),
                    "source_schema_version": _text(record.get("schema_version")),
                    "source_producer": _source_producer(gate, record),
                    "claim_id": _text(gate.get("claim_id")),
                    "next_action": _text(gate.get("next_action"))
                    or "Resolve the scorecard gate before closeout.",
                }
            )
    raw_minimum_failures = record.get("minimum_closeout_gate_failures")
    if isinstance(raw_minimum_failures, Sequence) and not isinstance(
        raw_minimum_failures, str | bytes
    ):
        for failure in raw_minimum_failures:
            code = _text(failure) or f"{surface}_minimum_closeout_gate_failed"
            blockers.append(
                {
                    "code": f"closeout_{surface}_observed_blocker",
                    "upstream_issue_code": code,
                    "message": f"{surface} minimum closeout gate failed: {code}.",
                    "source_module_id": f"{surface}_surface",
                    "source_reader_contract": f"polisyos.runtime.quality.{surface}",
                    "source_status": status,
                    "source_schema_version": _text(record.get("schema_version")),
                    "source_producer": _source_producer(record, record),
                    "next_action": (
                        f"Resolve the {surface} minimum closeout gate before closeout."
                    ),
                }
            )
    return blockers


def _surface_issues(blockers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for blocker in blockers:
        issues.append(
            _issue(
                _text(blocker.get("code")) or "closeout_surface_observed_blocker",
                _text(blocker.get("message")) or "Observed surface reported a blocker.",
                next_action=_text(blocker.get("next_action"))
                or "Resolve the observed surface blocker before closeout.",
                source_module_id=_text(blocker.get("source_module_id")),
                upstream_issue_code=_text(blocker.get("upstream_issue_code")),
                claim_id=_text(blocker.get("claim_id")),
            )
        )
    return issues


def _integration_verdict(status: str) -> str:
    if status == "closed_with_limitations":
        return "can_closeout_with_limitations"
    if status == "closed_with_accepted_deficits":
        return "can_closeout_with_accepted_deficits"
    if status == "closed":
        return "can_closeout"
    return "cannot_closeout"


def _integration_closeout_effect(
    *,
    status: str,
    accepted_deficits: Sequence[Mapping[str, Any]],
    limitations: Sequence[Mapping[str, Any]],
) -> str:
    if status == "blocked":
        return "closeout_blocked"
    if status == "incomplete":
        return "integration_incomplete"
    if limitations:
        return "limited_closeout"
    if accepted_deficits:
        return "accepted_deficit"
    return "closeout_allowed"


def _integration_records_from_quality_dir(quality_dir: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for module_id, filenames in CLOSEOUT_INTEGRATION_REPORT_FILES.items():
        for filename in filenames:
            payload = _load_json_or_none(quality_dir / filename)
            if isinstance(payload, Mapping):
                if module_id == "prompt_tool_repair_fmea":
                    from polisyos.runtime.quality.prompt_tool_ledger import (
                        prompt_tool_repair_fmea_closeout_record,
                    )

                    records[module_id] = prompt_tool_repair_fmea_closeout_record(payload)
                else:
                    records[module_id] = dict(payload)
                break
    return records


def _load_json_or_none(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _closeout_authority_envelope(*, run_id: str | None) -> dict[str, Any]:
    return {
        "authority_role": "closeout_reader_authority",
        "evidence_class": "closeout_verdict_only",
        "provenance_kind": "runtime_reader",
        "reader_contract": CLOSEOUT_READER_CONTRACT_ID,
        "reader_contract_version": CLOSEOUT_READER_CONTRACT_VERSION,
        "authoritative_for": list(_CLOSEOUT_ONLY_AUTHORITY),
        "may_not_use_for": list(_CLOSEOUT_MAY_NOT_USE_FOR),
        "may_not_be_used_for": list(_CLOSEOUT_MAY_NOT_USE_FOR),
        "run_id": _text(run_id),
    }


def _issue(
    code: str,
    message: str,
    *,
    severity: str = "fail",
    next_action: str,
    **extra: object,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "blocking": severity in {"fail", "incomplete"},
        "message": message,
        "next_action": next_action,
        **{key: value for key, value in extra.items() if value not in (None, "", [])},
    }


def _status(record: Mapping[str, Any]) -> str | None:
    value = (
        record.get("status")
        or record.get("quality_status")
        or record.get("closeout_status")
        or record.get("verdict")
    )
    text = _text(value)
    return text.casefold() if text else None


def _surface(record: Mapping[str, Any]) -> str | None:
    return _text(
        record.get("surface")
        or record.get("surface_kind")
        or record.get("artifact_kind")
        or record.get("source")
    )


def _forbidden_uses(record: Mapping[str, Any]) -> set[str]:
    raw = record.get("may_not_use_for") or record.get("may_not_be_used_for") or ()
    if isinstance(raw, str):
        return {raw.strip().casefold()} if raw.strip() else set()
    if isinstance(raw, Sequence):
        return {_text(item).casefold() for item in raw if _text(item)}
    return set()


def _child_issue_codes(record: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    for issue in record.get("issues") or ():
        if not isinstance(issue, Mapping):
            continue
        code = _text(issue.get("code"))
        if code:
            codes.append(code)
    return codes


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [row for row in value.values() if isinstance(row, Mapping)]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [row for row in value if isinstance(row, Mapping)]
    return []


def _source_producer(
    source: Mapping[str, Any],
    record: Mapping[str, Any] | None,
) -> str | None:
    return _text(
        source.get("producer")
        or source.get("producer_ref")
        or source.get("source_producer")
        or (record or {}).get("producer")
        or (record or {}).get("producer_ref")
        or (record or {}).get("reader_contract")
    )


def _first_text(value: object) -> str | None:
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, Sequence):
        for item in value:
            text = _text(item)
            if text:
                return text
    return None


def _closeout_effect_issue_code(effect: str) -> str:
    if effect == "review_required":
        return "closeout_deficit_review_required"
    if effect == "reissue_required":
        return "closeout_deficit_reissue_required"
    return "closeout_deficit_blocked"


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "CLOSEOUT_INTEGRATION_REPORT_FILES",
    "CLOSEOUT_INTEGRATION_SCHEMA_VERSION",
    "CLOSEOUT_READER_CONTRACT_ID",
    "CLOSEOUT_READER_CONTRACT_VERSION",
    "CLOSEOUT_READER_SCHEMA_VERSION",
    "DEFAULT_CLOSEOUT_INTEGRATION_MODULE_READERS",
    "DEFAULT_CLOSEOUT_MODULE_READERS",
    "CloseoutModuleReaderSpec",
    "build_can_i_closeout_verdict",
    "build_can_i_closeout_verdict_from_bundle_dir",
    "build_closeout_reader_skeleton",
    "build_closeout_reader_skeleton_from_bundle_dir",
]
