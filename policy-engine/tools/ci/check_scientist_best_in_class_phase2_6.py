#!/usr/bin/env python3
"""Validate Scientist best-in-class Phase 2.6 continuous governance."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase2_6"
TOOL_NAME = "ci.check-scientist-best-in-class-phase2-6"

REFERENCE_DOC = Path("docs/reference/scientist/continuous-governance.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
READINESS_DOC = Path("docs/reference/scientist/best-in-class-readiness.md")
INVENTORY_DOC = Path("docs/reference/scientist/scientist-capability-inventory.md")
SCIENTIST_INDEX_DOC = Path("docs/reference/scientist/index.md")
WAVE2_CONTRACT_DOC = Path("docs/reference/scientist/wave2-runtime-contracts.md")
MKDOCS_CONFIG = Path("mkdocs.yml")

REQUIRED_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/continuous_governance/__init__.py"),
    Path("src/polisyos/scientist/continuous_governance/monitors.py"),
    Path("src/polisyos/scientist/continuous_governance/invalidation.py"),
    Path("src/polisyos/scientist/continuous_governance/reissue.py"),
    Path("src/polisyos/scientist/continuous_governance/incident.py"),
    Path("src/polisyos/scientist/continuous_governance/reports.py"),
    REFERENCE_DOC,
    Path("tools/ci/check_scientist_best_in_class_phase2_6.py"),
    Path("tests/unit/scientist/continuous_governance/test_monitors.py"),
    Path("tests/unit/scientist/continuous_governance/test_invalidation.py"),
    Path("tests/unit/scientist/continuous_governance/test_reissue.py"),
    Path("tests/unit/scientist/continuous_governance/test_incident.py"),
    Path("tests/unit/scientist/continuous_governance/test_reports.py"),
    Path("tests/unit/scientist/continuous_governance/test_governance_integration.py"),
    Path("tests/tools/test_scientist_best_in_class_phase2_6.py"),
)
REFERENCE_TOKENS: tuple[str, ...] = (
    "DecisionValidityStatus",
    "GovernanceMonitorEvent",
    "GovernanceMonitorRecommendation",
    "ContinuousInvalidationResult",
    "ReissuePacket",
    "IncidentReport",
    "WithdrawalRecord",
    "DecisionValidityReport",
    "source invalidation",
    "Claim Ledger",
    "Research DAG",
    "continuous_governance_report_ref",
    "reissue_packet_ref",
    "withdrawal_record_ref",
    "hidden benchmark",
    "scientist.best_in_class.wave2.phase2_6.continuous_governance",
    "scientist.best_in_class.wave2.phase2_6.enable_reissue_workflow",
    "scientist.best_in_class.wave2.phase2_6.enable_withdrawal_status",
)
PLAN_TOKENS: tuple[str, ...] = (
    "Фаза 2.6 - Continuous governance and reissue loop",
    "closed",
    "check_scientist_best_in_class_phase2_6.py",
)
READINESS_TOKENS: tuple[str, ...] = (
    "Phase 2.6 - Continuous governance and reissue loop",
    "continuous-governance.md",
    "continuous_governance_reissue",
    "check_scientist_best_in_class_phase2_6.py",
    "closed",
)
INDEX_TOKENS: tuple[str, ...] = (
    "continuous-governance.md",
    "Continuous governance and reissue",
)
WAVE2_TOKENS: tuple[str, ...] = (
    "Phase 2.6 - Continuous governance and reissue loop",
    "closed",
    "continuous_governance",
    "check_scientist_best_in_class_phase2_6.py",
)
MKDOCS_TOKENS: tuple[str, ...] = ("reference/scientist/continuous-governance.md",)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _missing_tokens(repo_root: Path, path: Path, tokens: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}:{token}" for token in tokens if not _contains(repo_root / path, token)]


def _run_phase2_5_gate(repo_root: Path) -> tuple[bool, dict[str, Any], list[str]]:
    try:
        module = importlib.import_module("tools.ci.check_scientist_best_in_class_phase2_5")
    except Exception as exc:  # pragma: no cover - surfaced in payload.
        return (
            False,
            {"passes_all": False},
            [f"phase2_5_gate_import_failed:{exc.__class__.__name__}:{exc}"],
        )
    with TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "phase2_5.json"
        try:
            exit_code = module.main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--output",
                    str(output_path),
                    "--output-format",
                    "json",
                    "--require-passing",
                ]
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - surfaced in payload.
            return (
                False,
                {"passes_all": False},
                [f"phase2_5_gate_run_failed:{exc.__class__.__name__}:{exc}"],
            )
    notes: list[str] = []
    if exit_code != 0 or payload.get("passes_all") is not True:
        notes.append("phase2_5_gate_failed")
        notes.extend(f"phase2_5:{note}" for note in payload.get("notes", []))
    return not notes, payload, notes


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    notes: list[str] = []
    try:
        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.scientist.claims.lifecycle import (
            AppendOnlyClaimLedger,
            ClaimLifecycleAction,
        )
        from polisyos.scientist.claims.models import (
            ClaimPublishability,
            ClaimRecord,
            ClaimSupportStatus,
            ClaimType,
        )
        from polisyos.scientist.continuous_governance import (
            DecisionValidityStatus,
            ReissuePacket,
            WithdrawalRecord,
            build_drift_monitor_event,
            build_reissue_packet,
            build_validity_report,
            build_withdrawal_record,
            export_public_validity_report,
            load_reissue_packet,
            load_validity_report,
            load_withdrawal_record,
            mark_dependent_claims_stale,
            persist_reissue_packet,
            persist_validity_report,
            persist_withdrawal_record,
            recommend_validity_action,
        )
        from polisyos.scientist.continuous_governance.invalidation import (
            governance_event_from_source_invalidation,
        )
        from polisyos.scientist.governance.report import (
            GovernanceReport,
            GovernanceReportLinks,
        )
        from polisyos.scientist.research_dag.builder import ResearchDAGBuilder
        from polisyos.scientist.research_dag.invalidation import (
            SourceInvalidationEvent,
            SourceInvalidationImpact,
            propagate_source_invalidation,
        )
        from polisyos.scientist.research_dag.models import ResearchEdgeType, ResearchNodeType
        from polisyos.scientist.search.readiness import DecisionReadiness
        from pydantic import ValidationError
    except Exception as exc:  # pragma: no cover - surfaced in payload.
        return False, [f"phase2_6_import_failed:{exc.__class__.__name__}:{exc}"]

    def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
        import hashlib

        return ArtifactRef(
            artifact_id=ArtifactID.model_validate(
                "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()
            ),
            kind=kind,
            media_type="application/json",
        )

    source_ref = _ref("source", kind="scientist.source")
    builder = ResearchDAGBuilder(run_id="run_phase2_6", workflow_id="scientist_policy_design")
    source_node = builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="safe_fetch",
        summary="Read source.",
        artifact_refs=[source_ref],
    )
    extraction_node = builder.add_node(
        node_type=ResearchNodeType.EXTRACTION,
        producer="extractor",
        summary="Extract claim support.",
        claim_ids=["claim_1"],
    )
    builder.add_edge(
        source_node_id=source_node.node_id,
        target_node_id=extraction_node.node_id,
        edge_type=ResearchEdgeType.SUPPORTS,
        claim_ids=["claim_1"],
    )
    impact = propagate_source_invalidation(
        builder.artifact(),
        SourceInvalidationEvent(
            event_id="source_invalid_1",
            source_ref=source_ref,
            invalidation_type="stale",
            reason="Source freshness TTL expired.",
        ),
    )
    claim = ClaimRecord(
        claim_id="claim_1",
        run_id="run_phase2_6",
        claim_type=ClaimType.FACTUAL,
        text="Fixture claim.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        evidence_refs=[source_ref],
    )
    ledger = AppendOnlyClaimLedger(run_id="run_phase2_6", current_claims=[claim])
    invalidation_result = mark_dependent_claims_stale(
        ledger=ledger,
        decision_packet_ref=_ref("packet", kind="scientist.decision_packet"),
        impact=impact,
        actor_id="continuous_governance.monitor",
    )
    if invalidation_result.lifecycle_events[0].action is not ClaimLifecycleAction.MARKED_STALE:
        notes.append("source_invalidation_did_not_mark_claim_stale")
    if invalidation_result.recommendation.status is not DecisionValidityStatus.STALE:
        notes.append("stale_source_recommendation_not_stale")

    empty_impact = SourceInvalidationImpact(
        run_id="run_phase2_6",
        workflow_id="scientist_policy_design",
        event=SourceInvalidationEvent(
            event_id="source_invalid_orphan",
            source_ref=source_ref,
            invalidation_type="stale",
            reason="No lineage.",
        ),
        claim_lifecycle_action=ClaimLifecycleAction.MARKED_STALE,
    )
    try:
        governance_event_from_source_invalidation(
            decision_packet_ref=_ref("packet", kind="scientist.decision_packet"),
            impact=empty_impact,
        )
    except ValueError:
        pass
    else:
        notes.append("source_invalidation_without_lineage_not_blocked")

    drift_event = build_drift_monitor_event(
        decision_packet_ref=_ref("packet", kind="scientist.decision_packet"),
        event_type="fairness_drift",
        severity="warning",
        reason="Fairness drift crossed warning threshold.",
        affected_claim_ids=["claim_1"],
    )
    drift_recommendation = recommend_validity_action(drift_event)
    if not drift_recommendation.human_review_required:
        notes.append("drift_monitor_did_not_trigger_review")
    block_event = build_drift_monitor_event(
        decision_packet_ref=_ref("packet", kind="scientist.decision_packet"),
        event_type="calibration_drift",
        severity="block",
        reason="Calibration drift crossed block threshold.",
        affected_claim_ids=["claim_1"],
    )
    if not recommend_validity_action(block_event).reissue_recommended:
        notes.append("blocking_drift_did_not_trigger_reissue")

    monitor_ref = _ref("monitor", kind="scientist.governance_monitor_event")
    reissue = build_reissue_packet(
        original_decision_packet_ref=_ref("old-packet", kind="scientist.decision_packet"),
        original_claim_ledger_ref=_ref("old-ledger", kind="scientist.claim_ledger_v2"),
        new_decision_packet_ref=_ref("new-packet", kind="scientist.decision_packet"),
        new_claim_ledger_ref=_ref("new-ledger", kind="scientist.claim_ledger_v2"),
        status=DecisionValidityStatus.REISSUED,
        monitor_event_refs=[monitor_ref],
        reason="Reissued after source invalidation.",
    )
    if reissue.original_claim_ledger_ref == reissue.new_claim_ledger_ref:
        notes.append("reissue_old_new_ledger_links_missing")
    try:
        ReissuePacket(
            original_decision_packet_ref=_ref("old-packet", kind="scientist.decision_packet"),
            status=DecisionValidityStatus.REVIEW_REQUIRED,
            monitor_event_refs=[monitor_ref],
            reason="Missing ledger.",
        )
    except ValidationError:
        pass
    else:
        notes.append("reissue_without_original_ledger_not_blocked")

    try:
        WithdrawalRecord(
            withdrawal_id="withdrawal_missing_audit",
            decision_packet_ref=_ref("old-packet", kind="scientist.decision_packet"),
            actor_id="reviewer",
            reason="Missing audit event.",
            monitor_event_refs=[monitor_ref],
        )
    except ValidationError:
        pass
    else:
        notes.append("withdrawal_without_audit_event_not_blocked")
    withdrawal = build_withdrawal_record(
        withdrawal_id="withdrawal_1",
        decision_packet_ref=_ref("old-packet", kind="scientist.decision_packet"),
        actor_id="reviewer",
        reason="Withdraw after incident review.",
        audit_event_ref=_ref("audit", kind="scientist.audit_event"),
        monitor_event_refs=[monitor_ref],
    )
    if withdrawal.actor_id != "reviewer" or not withdrawal.reason:
        notes.append("withdrawal_audit_metadata_missing")

    report = build_validity_report(
        decision_packet_ref=_ref("packet", kind="scientist.decision_packet"),
        monitor_events=[drift_event],
        reissue_packet_ref=_ref("reissue", kind="scientist.reissue_packet"),
        hidden_internal_ref_ids=["hidden_holdout_suite"],
    )
    public_export = export_public_validity_report(report)
    if "hidden_holdout_suite" in json.dumps(public_export, sort_keys=True):
        notes.append("public_validity_export_leaked_hidden_ref")
    hidden_report = build_validity_report(
        decision_packet_ref=_ref("hidden", kind="scientist.hidden_eval.decision_packet"),
        monitor_events=[drift_event],
    )
    try:
        export_public_validity_report(hidden_report)
    except ValueError:
        pass
    else:
        notes.append("public_validity_export_hidden_ref_not_blocked")

    governance = GovernanceReport(
        verdict="human_gate",
        links=GovernanceReportLinks(
            continuous_governance_report_ref=_ref(
                "validity",
                kind="scientist.continuous_governance_report",
            ),
            reissue_packet_ref=_ref("reissue", kind="scientist.reissue_packet"),
            withdrawal_record_ref=_ref("withdrawal", kind="scientist.withdrawal_record"),
        ),
    )
    if governance.links.reissue_packet_ref is None:
        notes.append("governance_report_reissue_link_missing")

    with TemporaryDirectory() as tmp:
        store = FileSystemCAS(Path(tmp))
        reissue_ref = persist_reissue_packet(store, reissue)
        if load_reissue_packet(store, reissue_ref) != reissue:
            notes.append("reissue_packet_cas_roundtrip_failed")
        withdrawal_ref = persist_withdrawal_record(store, withdrawal)
        if load_withdrawal_record(store, withdrawal_ref) != withdrawal:
            notes.append("withdrawal_record_cas_roundtrip_failed")
        report_ref = persist_validity_report(store, report)
        if load_validity_report(store, report_ref) != report:
            notes.append("validity_report_cas_roundtrip_failed")
    return not notes, notes


def _build_payload(repo_root: Path) -> dict[str, Any]:
    notes: list[str] = []
    missing_files = [str(path) for path in REQUIRED_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_file:{path}" for path in missing_files)

    phase2_5_ok, phase2_5_payload, phase2_5_notes = _run_phase2_5_gate(repo_root)
    notes.extend(phase2_5_notes)
    import_ok, import_notes = _import_and_validate(repo_root)
    notes.extend(import_notes)

    missing_reference_tokens = _missing_tokens(
        repo_root,
        REFERENCE_DOC,
        REFERENCE_TOKENS,
        "missing_reference_token",
    )
    notes.extend(missing_reference_tokens)
    missing_plan_tokens = _missing_tokens(
        repo_root,
        ACTIVE_PLAN_DOC,
        PLAN_TOKENS,
        "missing_active_plan_token",
    )
    notes.extend(missing_plan_tokens)
    missing_readiness_tokens = _missing_tokens(
        repo_root,
        READINESS_DOC,
        READINESS_TOKENS,
        "missing_readiness_token",
    )
    notes.extend(missing_readiness_tokens)
    missing_inventory_tokens = _missing_tokens(
        repo_root,
        INVENTORY_DOC,
        ("continuous-governance.md", "check_scientist_best_in_class_phase2_6.py"),
        "missing_inventory_token",
    )
    notes.extend(missing_inventory_tokens)
    missing_index_tokens = _missing_tokens(
        repo_root,
        SCIENTIST_INDEX_DOC,
        INDEX_TOKENS,
        "missing_scientist_index_token",
    )
    notes.extend(missing_index_tokens)
    missing_wave2_tokens = _missing_tokens(
        repo_root,
        WAVE2_CONTRACT_DOC,
        WAVE2_TOKENS,
        "missing_wave2_contract_token",
    )
    notes.extend(missing_wave2_tokens)
    missing_mkdocs_tokens = _missing_tokens(
        repo_root,
        MKDOCS_CONFIG,
        MKDOCS_TOKENS,
        "missing_mkdocs_token",
    )
    notes.extend(missing_mkdocs_tokens)

    category_results = {
        "deliverables_exist": not missing_files,
        "phase2_5_gate_green": phase2_5_ok,
        "continuous_governance_contracts_validate": import_ok,
        "reference_doc_complete": not missing_reference_tokens,
        "active_plan_updated": not missing_plan_tokens,
        "readiness_doc_updated": not missing_readiness_tokens,
        "inventory_doc_updated": not missing_inventory_tokens,
        "scientist_index_updated": not missing_index_tokens,
        "wave2_contract_updated": not missing_wave2_tokens,
        "mkdocs_nav_updated": not missing_mkdocs_tokens,
    }
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "phase2_5_gate_report": phase2_5_payload,
        "notes": notes,
    }


def _result(payload: dict[str, Any]) -> ToolResult:
    status = "ok" if payload.get("passes_all") else "failed"
    note_list = list(payload.get("notes", []))
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=(
            "Scientist best-in-class Phase 2.6 is accepted"
            if status == "ok"
            else "Scientist best-in-class Phase 2.6 is incomplete"
        ),
        exit_code=0 if status == "ok" else 1,
        messages=tuple(
            ToolMessage(
                level="error" if status == "failed" else "info",
                message=str(note),
                rule_id="SCIENTIST_BEST_IN_CLASS_PHASE2_6",
            )
            for note in note_list
        ),
        data=payload,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("json", "text"), default="text")
    parser.add_argument("--require-passing", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    payload = _build_payload(repo_root)
    result = _result(payload)
    rendered = (
        json.dumps(payload, indent=2, sort_keys=True)
        if args.output_format == "json"
        else format_tool_result(result)
    )
    if args.output is not None:
        atomic_write_text(args.output, rendered + "\n")
    else:
        print(rendered)
    return 0 if result.exit_code == 0 or not args.require_passing else result.exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
