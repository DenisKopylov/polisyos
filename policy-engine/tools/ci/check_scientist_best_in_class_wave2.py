#!/usr/bin/env python3
"""Validate the Scientist Wave 2 best-in-class closeout surface."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_wave2"
TOOL_NAME = "ci.check-scientist-best-in-class-wave2"

ACCEPTANCE_DOC = Path("docs/reference/scientist/best-in-class-wave2-acceptance.md")
MATURITY_DOC = Path("docs/reference/scientist/best-in-class-maturity.md")
MIGRATION_DOC = Path("docs/reference/scientist/wave2-migration-notes.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
READINESS_DOC = Path("docs/reference/scientist/best-in-class-readiness.md")
INVENTORY_DOC = Path("docs/reference/scientist/scientist-capability-inventory.md")
SCIENTIST_INDEX_DOC = Path("docs/reference/scientist/index.md")
WAVE2_CONTRACT_DOC = Path("docs/reference/scientist/wave2-runtime-contracts.md")
MKDOCS_CONFIG = Path("architecture/tooling/mkdocs/generated.yml")

PHASE_GATE_MODULES: tuple[tuple[str, str], ...] = (
    ("phase2_0", "tools.ci.check_scientist_best_in_class_phase2_0"),
    ("phase2_1", "tools.ci.check_scientist_best_in_class_phase2_1"),
    ("phase2_2", "tools.ci.check_scientist_best_in_class_phase2_2"),
    ("phase2_3", "tools.ci.check_scientist_best_in_class_phase2_3"),
    ("phase2_4", "tools.ci.check_scientist_best_in_class_phase2_4"),
    ("phase2_5", "tools.ci.check_scientist_best_in_class_phase2_5"),
    ("phase2_6", "tools.ci.check_scientist_best_in_class_phase2_6"),
    ("phase2_7", "tools.ci.check_scientist_best_in_class_phase2_7"),
)

REQUIRED_FILES: tuple[Path, ...] = (
    ACCEPTANCE_DOC,
    MATURITY_DOC,
    MIGRATION_DOC,
    Path("tools/ci/check_scientist_best_in_class_wave2.py"),
    Path("tests/repo_quality/tools/test_scientist_best_in_class_wave2.py"),
)
ACCEPTANCE_TOKENS: tuple[str, ...] = (
    "Wave 2 acceptance",
    "Claim Ledger lifecycle",
    "Research DAG replay",
    "VOI",
    "reflexive memory",
    "challenge factory",
    "continuous governance",
    "decision-grade compiler",
    "shadow_evidence_status: measured",
    "quality_lift:",
    "cost_reduction:",
    "safety_improvement:",
    "residual risks",
    "check_scientist_best_in_class_wave2.py",
)
MATURITY_TOKENS: tuple[str, ...] = (
    "best-in-class maturity",
    "Maturity level",
    "claim ledger",
    "research DAG",
    "benchmark authority",
    "human review",
    "continuous governance",
    "decision-grade compiler",
    "Wave 2 closeout",
)
MIGRATION_TOKENS: tuple[str, ...] = (
    "claim_ledger_v2_ref",
    "claim_ledger_diff_ref",
    "claim_export_ref",
    "blocked_claim_summary_ref",
    "research_dag_replay_ref",
    "research_dag_diff_ref",
    "research_source_invalidation_ref",
    "voi_report_ref",
    "source_voi_ref",
    "human_review_voi_ref",
    "compute_budget_decision_ref",
    "memory_retrieval_ref",
    "memory_event_ref",
    "memory_influence_dag_ref",
    "lesson_revocation_ref",
    "challenge_factory_report_ref",
    "challenge_pack_lineage_ref",
    "rotating_challenge_freshness_ref",
    "continuous_governance_report_ref",
    "reissue_packet_ref",
    "withdrawal_record_ref",
    "incident_report_ref",
    "monitor_event_ref",
    "decision_grade_export_ref",
    "public_summary_ref",
    "reviewer_packet_ref",
    "expert_appendix_ref",
    "machine_export_ref",
    "frontend_trust_view",
    "scientist.best_in_class.wave2.phase2_1.claim_ledger_v2",
    "scientist.best_in_class.wave2.phase2_1.require_lifecycle_events",
    "scientist.best_in_class.wave2.phase2_2.replay_plan",
    "scientist.best_in_class.wave2.phase2_2.source_invalidation",
    "scientist.best_in_class.wave2.phase2_3.voi_reports",
    "scientist.best_in_class.wave2.phase2_3.voi_scheduler_shadow",
    "scientist.best_in_class.wave2.phase2_3.voi_scheduler_default",
    "scientist.best_in_class.wave2.phase2_4.reflexive_memory",
    "scientist.best_in_class.wave2.phase2_4.memory_influence_shadow",
    "scientist.best_in_class.wave2.phase2_4.memory_influence_default",
    "scientist.best_in_class.wave2.phase2_5.challenge_factory",
    "scientist.best_in_class.wave2.phase2_5.require_fresh_rotating_challenge",
    "scientist.best_in_class.wave2.phase2_6.continuous_governance",
    "scientist.best_in_class.wave2.phase2_6.enable_reissue_workflow",
    "scientist.best_in_class.wave2.phase2_6.enable_withdrawal_status",
    "scientist.best_in_class.wave2.phase2_7.decision_grade_compiler",
    "scientist.best_in_class.wave2.phase2_7.compiler_backed_decision_card",
    "scientist.best_in_class.wave2.phase2_8.wave2_acceptance_gate",
    "Rollback",
)
PLAN_TOKENS: tuple[str, ...] = (
    "Фаза 2.8 - System closeout",
    "closed",
    "best-in-class-wave2-acceptance.md",
    "check_scientist_best_in_class_wave2.py",
)
READINESS_TOKENS: tuple[str, ...] = (
    "Phase 2.8 - System closeout",
    "best-in-class-wave2-acceptance.md",
    "best-in-class-maturity.md",
    "wave2-migration-notes.md",
    "check_scientist_best_in_class_wave2.py",
    "closed",
)
INDEX_TOKENS: tuple[str, ...] = (
    "best-in-class-wave2-acceptance.md",
    "best-in-class-maturity.md",
    "wave2-migration-notes.md",
    "Wave 2 acceptance",
)
WAVE2_TOKENS: tuple[str, ...] = (
    "Phase 2.8 - System closeout",
    "closed",
    "best-in-class-wave2-acceptance.md",
    "wave2-migration-notes.md",
    "check_scientist_best_in_class_wave2.py",
)
MKDOCS_TOKENS: tuple[str, ...] = (
    "reference/scientist/best-in-class-wave2-acceptance.md",
    "reference/scientist/best-in-class-maturity.md",
    "reference/scientist/wave2-migration-notes.md",
)
UNRESOLVED_MIGRATION_TOKENS: tuple[str, ...] = (
    "TODO",
    "TBD",
    "unresolved_migration",
    "unresolved migration",
)
SHADOW_EVIDENCE_RE = re.compile(
    r"(quality_lift|cost_reduction|safety_improvement)\s*:\s*[+-]?\d+(?:\.\d+)?(?:%|pp)"
)


class _ArtifactRefLike(Protocol):
    artifact_id: object
    kind: str
    media_type: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _missing_tokens(repo_root: Path, path: Path, tokens: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}:{token}" for token in tokens if not _contains(repo_root / path, token)]


def _run_gate_module(
    *,
    repo_root: Path,
    gate_id: str,
    module_name: str,
) -> tuple[bool, dict[str, Any], list[str]]:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return (
            False,
            {"passes_all": False},
            [f"{gate_id}:gate_import_failed:{exc.__class__.__name__}:{exc}"],
        )
    with TemporaryDirectory() as tmp:
        output_path = Path(tmp) / f"{gate_id}.json"
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
        except Exception as exc:  # pragma: no cover - surfaced in gate payload.
            return (
                False,
                {"passes_all": False},
                [f"{gate_id}:gate_run_failed:{exc.__class__.__name__}:{exc}"],
            )
    notes: list[str] = []
    if exit_code != 0 or payload.get("passes_all") is not True:
        notes.append(f"{gate_id}:gate_failed")
        notes.extend(f"{gate_id}:{note}" for note in payload.get("notes", []))
    return not notes, payload, notes


def _run_wave1_gate(repo_root: Path) -> tuple[bool, dict[str, Any], list[str]]:
    return _run_gate_module(
        repo_root=repo_root,
        gate_id="wave1",
        module_name="tools.ci.check_scientist_best_in_class_wave1",
    )


def _run_phase_gates(repo_root: Path) -> tuple[bool, dict[str, dict[str, Any]], list[str]]:
    reports: dict[str, dict[str, Any]] = {}
    notes: list[str] = []
    for phase_id, module_name in PHASE_GATE_MODULES:
        ok, payload, phase_notes = _run_gate_module(
            repo_root=repo_root,
            gate_id=phase_id,
            module_name=module_name,
        )
        reports[phase_id] = payload
        if not ok:
            notes.extend(phase_notes)
    return not notes, reports, notes


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    notes: list[str] = []
    try:
        from pydantic import ValidationError

        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.core.contracts.c4_persisted_profiles import c4_semantic_digest
        from polisyos.scientist.evals.challenge_factory import (
            ChallengeStatus,
            generate_challenge_from_failure_card,
            promote_generated_challenge,
            register_challenge_pack_with_benchmark_registry,
        )
        from polisyos.scientist.evidence.claims.diff import diff_claim_ledgers
        from polisyos.scientist.evidence.claims.export import (
            ClaimExportAudience,
            _format_resolved_claim_ledger,
        )
        from polisyos.scientist.evidence.claims.head_index import (
            CLAIM_LEDGER_AUTHORITY_PURPOSE,
            ClaimBridgePendingProjection,
            ClaimLedgerHeadStatement,
            ClaimLedgerOwnerKey,
            ClaimLedgerOwnerKeyDerivationInput,
            PersistedClaimLedgerHead,
            derive_claim_ledger_owner_scope_ref,
        )
        from polisyos.scientist.evidence.claims.lifecycle import (
            build_initial_append_only_ledger,
            lifecycle_status_for_ledger,
        )
        from polisyos.scientist.evidence.claims.models import (
            ClaimLedger,
            ClaimPublishability,
            ClaimRecord,
            ClaimSupportStatus,
            ClaimType,
        )
        from polisyos.scientist.governance.continuous import DecisionValidityStatus
        from polisyos.scientist.governance.continuous.monitors import build_drift_monitor_event
        from polisyos.scientist.governance.continuous.reissue import (
            ReissuePacket,
            build_reissue_packet,
        )
        from polisyos.scientist.governance.human_review.models import ReviewRiskTier
        from polisyos.scientist.governance.human_review.oversight_policy import (
            HumanReviewRequirement,
        )
        from polisyos.scientist.governance.human_review.voi_escalation import (
            build_human_escalation_voi_decision,
            validate_human_escalation_voi_decision,
        )
        from polisyos.scientist.methods.research_dag.builder import ResearchDAGBuilder
        from polisyos.scientist.methods.research_dag.comparison import compare_research_trajectories
        from polisyos.scientist.methods.research_dag.models import (
            ResearchEdgeType,
            ResearchNodeType,
        )
        from polisyos.scientist.methods.research_dag.projections import (
            project_reflexive_memory_events_to_research_dag,
            validate_memory_influence_dag_attribution,
        )
        from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
        from polisyos.scientist.methods.search.failure_cards import (
            FailureSeverity,
            TypedFailureCard,
        )
        from polisyos.scientist.methods.search.lessons import LessonCard, LessonKind
        from polisyos.scientist.methods.search.readiness import DecisionReadiness
        from polisyos.scientist.methods.search.voi_models import (
            VOIDecisionRecord,
            VOIDecisionType,
            VOIRunReport,
        )
        from polisyos.scientist.orchestration.memory import (
            MemoryApplicabilityContext,
            MemoryContaminationPolicy,
            MemoryVisibility,
            apply_reflexive_scope,
            assert_reusable_memory_clean,
            retrieve_reflexive_lessons,
        )
        from polisyos.scientist.publishing.publisher import (
            DecisionGradeExport,
            OutputAudience,
            assert_decision_grade_exports_consistent,
            compile_decision_grade_exports,
        )
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return False, [f"wave2_import_failed:{exc.__class__.__name__}:{exc}"]

    def ref(seed: str, *, kind: str = "scientist.fixture") -> ArtifactRef:
        return ArtifactRef(
            artifact_id=ArtifactID.model_validate(
                "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()
            ),
            kind=kind,
            media_type="application/json",
        )

    run_id = "run_wave2_closeout"
    workflow_id = "scientist_policy_design"
    claims_ref = ref("claims-v2", kind="scientist.claim_ledger_v2")
    dag_ref = ref("research-dag", kind="scientist.research_dag")
    evidence_ref = ref("evidence", kind="scientist.source")
    claim_public = ClaimRecord(
        claim_id="claim_public",
        run_id=run_id,
        claim_type=ClaimType.FACTUAL,
        text="Approved policy claim.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.PUBLISHABLE,
        readiness_level=DecisionReadiness.ANALYST_ADVISORY,
        evidence_refs=[evidence_ref],
        source_attribution=["source:evidence"],
    )
    claim_blocked = ClaimRecord(
        claim_id="claim_blocked",
        run_id=run_id,
        claim_type=ClaimType.FACTUAL,
        text="Blocked policy claim.",
        support_status=ClaimSupportStatus.CONTESTED,
        publishability=ClaimPublishability.BLOCKED,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        evidence_refs=[evidence_ref],
        counterevidence_refs=[ref("counterevidence", kind="scientist.source")],
        blocked_reasons=["counterevidence unresolved"],
    )
    ledger = build_initial_append_only_ledger(
        ClaimLedger(run_id=run_id, claims=[claim_public, claim_blocked]),
        actor_id="wave2.closeout",
        reason="Wave 2 closeout fixture lifecycle initialization.",
    )
    machine_export = _format_resolved_claim_ledger(
        ledger,
        audience=ClaimExportAudience.MACHINE,
        pending_projection=ClaimBridgePendingProjection(
            completed_batch_denominator_established=True,
        ),
    )
    event_claim_ids = {event.claim_id for event in ledger.events}
    export_claim_ids = {claim.claim_id for claim in machine_export.claims}
    for claim in ledger.current_claims:
        if claim.claim_id not in event_claim_ids:
            notes.append(f"claim_lifecycle_state_missing:{claim.claim_id}")
        if claim.claim_id not in export_claim_ids:
            notes.append(f"claim_export_status_missing:{claim.claim_id}")
    if lifecycle_status_for_ledger(ledger) != "available":
        notes.append("claim_ledger_lifecycle_not_available")

    def dag_with(
        *,
        dag_run_id: str,
        claim_id: str,
        source_ref: ArtifactRef,
        snippet_id: str,
        verdict: str,
        claim_ledger_ref: ArtifactRef | None = None,
        claim_ids: list[str] | None = None,
    ) -> object:
        node_claim_ids = claim_ids or [claim_id]
        builder = ResearchDAGBuilder(
            run_id=dag_run_id,
            workflow_id=workflow_id,
            claim_ledger_ref=claim_ledger_ref,
            created_at=datetime(2026, 4, 28, tzinfo=UTC),
        )
        question = builder.add_node(
            node_type=ResearchNodeType.QUESTION,
            producer="planner",
            summary="Closeout fixture research question.",
            metadata={"query": "wave2 closeout"},
        )
        source = builder.add_node(
            node_type=ResearchNodeType.SOURCE_READ,
            producer="safe_fetch",
            summary="Read pinned source.",
            artifact_refs=[source_ref],
        )
        extraction = builder.add_node(
            node_type=ResearchNodeType.EXTRACTION,
            producer="extractor",
            summary="Extract snippet.",
            metadata={"snippet_id": snippet_id},
            claim_ids=node_claim_ids,
        )
        synthesis = builder.add_node(
            node_type=ResearchNodeType.SYNTHESIS,
            producer="compiler",
            summary="Synthesize decision claim.",
            claim_ids=node_claim_ids,
        )
        governance = builder.add_node(
            node_type=ResearchNodeType.GOVERNANCE,
            producer="governance",
            summary=f"Governance {verdict}.",
            metadata={"verdict": verdict},
            claim_ids=node_claim_ids,
        )
        for previous, current in (
            (question, source),
            (source, extraction),
            (extraction, synthesis),
            (synthesis, governance),
        ):
            builder.add_edge(
                source_node_id=previous.node_id,
                target_node_id=current.node_id,
                edge_type=ResearchEdgeType.DEPENDS_ON,
                claim_ids=node_claim_ids,
            )
        return builder.artifact()

    old_dag = dag_with(
        dag_run_id="run_wave2_old",
        claim_id="claim_old",
        source_ref=ref("old-source", kind="scientist.source"),
        snippet_id="snippet_old",
        verdict="human_gate",
    )
    new_dag = dag_with(
        dag_run_id="run_wave2_new",
        claim_id="claim_public",
        source_ref=evidence_ref,
        snippet_id="snippet_new",
        verdict="pass",
        claim_ids=["claim_public", "claim_blocked"],
    )
    comparison = compare_research_trajectories(old_dag, new_dag)
    if not comparison.changed_sources:
        notes.append("replay_diff_missing_changed_sources")
    if "added:claim_public" not in comparison.changed_claim_ids:
        notes.append("replay_diff_missing_changed_claim")
    if not any("pass" in item for item in comparison.changed_governance_outcomes):
        notes.append("replay_diff_missing_changed_governance")

    before_ledger = build_initial_append_only_ledger(
        ClaimLedger(
            run_id="run_wave2_old",
            claims=[
                ClaimRecord(
                    claim_id="claim_old",
                    run_id="run_wave2_old",
                    claim_type=ClaimType.FACTUAL,
                    text="Old internal claim.",
                    support_status=ClaimSupportStatus.SUPPORTED,
                    publishability=ClaimPublishability.INTERNAL_ONLY,
                    readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
                    evidence_refs=[ref("old-source", kind="scientist.source")],
                )
            ],
        ),
        actor_id="wave2.closeout",
        reason="Fixture before ledger.",
    )
    claim_diff = diff_claim_ledgers(before_ledger, ledger)
    missing_replay_claims = _claim_changes_missing_from_replay_diff(
        changed_claim_ids=set(claim_diff.added_claim_ids + claim_diff.removed_claim_ids),
        replay_changed_claim_ids=comparison.changed_claim_ids,
    )
    if missing_replay_claims:
        notes.append(f"claim_changes_missing_from_replay_diff:{','.join(missing_replay_claims)}")
    if not _claim_changes_missing_from_replay_diff(
        changed_claim_ids={"claim_without_replay"},
        replay_changed_claim_ids=comparison.changed_claim_ids,
    ):
        notes.append("claim_change_absent_from_replay_diff_not_detected")

    requirement = HumanReviewRequirement(
        required=True,
        risk_tier=ReviewRiskTier.HIGH,
        reasons=["high_risk_publication"],
    )
    good_voi = build_human_escalation_voi_decision(
        run_id=run_id,
        requirement=requirement,
        expected_harm=2.0,
        reversal_risk=0.4,
        review_cost=0.2,
    )
    voi_report = VOIRunReport(
        run_id=run_id,
        decisions=[good_voi],
        total_expected_cost=good_voi.expected_cost,
        calibration_status="shadow_calibrated",
    )
    if voi_report.decisions[0].recommended_action != "request_human_review":
        notes.append("mandatory_human_review_voi_not_requested")
    bad_voi = VOIDecisionRecord(
        decision_id="voi_bad_human_review",
        run_id=run_id,
        decision_type=VOIDecisionType.HUMAN_ESCALATION,
        recommended_action="defer",
        expected_value=0.0,
        expected_cost=0.0,
        expected_risk_reduction=0.0,
        explanation="Bad fixture attempts to skip required human review.",
    )
    if not validate_human_escalation_voi_decision(bad_voi, requirement=requirement):
        notes.append("voi_human_review_suppression_not_blocked")

    lesson = apply_reflexive_scope(
        LessonCard(
            lesson_id="lesson_wave2",
            kind=LessonKind.FAILURE,
            summary="Prior run skipped source verification.",
            failure_type="unsupported_claim",
            stage_name="evidence_gate",
            fidelity_level=2,
            candidate_hash="candidate",
            source_run_id="source_run",
            task_family="policy",
            domain="tax",
            anti_patterns=["unsupported_claim"],
            remediation_hint="Verify snippets before promotion.",
        ),
        visibility=MemoryVisibility.DOMAIN,
        domain="tax",
        workflow_id=workflow_id,
    )
    memory_result = retrieve_reflexive_lessons(
        [lesson],
        context=MemoryApplicabilityContext(
            run_id=run_id,
            domain="tax",
            workflow_id=workflow_id,
        ),
    )
    memory_dag = project_reflexive_memory_events_to_research_dag(
        memory_result.events,
        run_id=run_id,
        workflow_id=workflow_id,
        claim_ledger_ref=claims_ref,
    )
    memory_violations = validate_memory_influence_dag_attribution(
        memory_result.events,
        memory_dag,
    )
    if memory_violations:
        notes.extend(memory_violations)
    try:
        assert_reusable_memory_clean(
            {"lesson": "contains EVAL_CANARY_WAVE2"},
            policy=MemoryContaminationPolicy(canary_tokens={"EVAL_CANARY_WAVE2"}),
        )
    except ValueError:
        pass
    else:
        notes.append("memory_hidden_eval_canary_not_blocked")

    failure_card = TypedFailureCard(
        judge_name="citation_faithfulness",
        failure_type="forged_citation",
        severity=FailureSeverity.BLOCKER,
        description="The cited source did not support the claim.",
        remediation_hint="Generate forged-citation challenge.",
        evidence_ref=ref("failure-card", kind="scientist.failure_card"),
    )
    challenge = generate_challenge_from_failure_card(
        failure_card,
        run_id=run_id,
        prompt_or_case_ref=ref("challenge-case", kind="scientist.challenge_case"),
    )
    reviewed_challenge = promote_generated_challenge(
        challenge,
        status=ChallengeStatus.APPROVED_FOR_PRIVATE,
        reviewer_refs=[ref("challenge-review", kind="scientist.human_review_decision")],
    )
    with TemporaryDirectory() as tmp:
        registry = BenchmarkRegistry(Path(tmp) / "benchmarks")
        pack_ref = ref("rotating-pack", kind="scientist.benchmark_pack")
        register_challenge_pack_with_benchmark_registry(
            registry,
            split_type="rotating_challenge",
            pack_ref=pack_ref,
            challenges=[reviewed_challenge],
            family="policy_design",
            run_id=run_id,
            loop_id="loop-wave2",
            suite_id="wave2-rotating-v1",
        )
        snapshot = registry.snapshot()
    registered_lineage = [
        entry.metadata.get("challenge_pack_lineage")
        for entry in snapshot.entries
        if entry.artifact_ref == pack_ref
    ]
    if not registered_lineage:
        notes.append("reviewed_challenge_pack_not_registered")
    elif not registered_lineage[0].get("reviewer_ref_ids"):
        notes.append("registered_challenge_pack_missing_reviewer_lineage")

    monitor_ref = ref("monitor-event", kind="scientist.governance_monitor_event")
    reissue = build_reissue_packet(
        original_decision_packet_ref=ref("old-packet", kind="scientist.decision_packet"),
        original_claim_ledger_ref=ref("old-ledger", kind="scientist.claim_ledger_v2"),
        new_decision_packet_ref=ref("new-packet", kind="scientist.decision_packet"),
        new_claim_ledger_ref=claims_ref,
        status=DecisionValidityStatus.REISSUED,
        monitor_event_refs=[monitor_ref],
        reason="Reissued after Wave 2 closeout fixture invalidation.",
    )
    if reissue.original_claim_ledger_ref == reissue.new_claim_ledger_ref:
        notes.append("reissue_old_new_ledger_linkage_missing")
    try:
        ReissuePacket(
            original_decision_packet_ref=ref("old-packet", kind="scientist.decision_packet"),
            original_claim_ledger_ref=ref("old-ledger", kind="scientist.claim_ledger_v2"),
            new_decision_packet_ref=ref("new-packet", kind="scientist.decision_packet"),
            status=DecisionValidityStatus.REISSUED,
            monitor_event_refs=[monitor_ref],
            reason="Missing new ledger.",
        )
    except ValidationError:
        pass
    else:
        notes.append("reissue_without_new_ledger_not_blocked")

    governance_event = build_drift_monitor_event(
        decision_packet_ref=ref("new-packet", kind="scientist.decision_packet"),
        event_type="fairness_drift",
        severity="warning",
        reason="Fairness drift requires review.",
        affected_claim_ids=["claim_public"],
    )
    if governance_event.affected_claim_ids != ["claim_public"]:
        notes.append("continuous_governance_claim_link_missing")

    compiler_dag = dag_with(
        dag_run_id=run_id,
        claim_id="claim_public",
        source_ref=evidence_ref,
        snippet_id="snippet_public",
        verdict="human_gate",
        claim_ledger_ref=claims_ref,
    )

    derivation = ClaimLedgerOwnerKeyDerivationInput(
        base_claims_ref=claims_ref,
        base_claims_content_hash=str(claims_ref.artifact_id),
        requested_authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
    )
    claim_owner_key = ClaimLedgerOwnerKey(
        scope_ref=derive_claim_ledger_owner_scope_ref(derivation),
        claim_owner_ref="wave2-fixture-owner",
        authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
        derivation_input=derivation,
    )
    head_statement = ClaimLedgerHeadStatement(
        root_identity=str(ref("root-identity").artifact_id),
        root_receipt_ref=ref("root", kind="scientist.claims.ledger_root"),
        root_receipt_content_hash=str(ref("root-content").artifact_id),
        owner_key=claim_owner_key,
        ledger_artifact_ref=claims_ref,
        ledger_raw_cas_hash=str(claims_ref.artifact_id),
        generation=0,
        predecessor_head_ref=None,
        bridge_result_refs=(),
        issuance_verifier_receipt_ref=ref(
            "issuance-verifier",
            kind="scientist.claims.ledger_root_verification",
        ),
        issuance_verifier_receipt_content_hash=str(ref("issuance-verifier-content").artifact_id),
    )

    class _FixtureClaimOwner:
        head = PersistedClaimLedgerHead(
            head_ref=ref("head", kind="scientist.claims.ledger_head"),
            head_content_hash=c4_semantic_digest("claim_ledger_head", head_statement),
            statement=head_statement,
        )

        def resolve_current(self, *, owner_key: object) -> object:
            del owner_key
            return self.head

        def export_current(
            self,
            *,
            owner_key: object,
            audience: ClaimExportAudience,
        ) -> object:
            del owner_key
            return _format_resolved_claim_ledger(
                ledger,
                audience=audience,
                pending_projection=ClaimBridgePendingProjection(
                    completed_batch_denominator_established=True,
                ),
            )

    claim_owner = _FixtureClaimOwner()
    exports = compile_decision_grade_exports(
        run_id=run_id,
        research_dag_ref=dag_ref,
        claim_owner=claim_owner,
        claim_owner_key=claim_owner_key,
        research_dag=compiler_dag,
        decision_payload={"policy_summary": "Approved policy claim."},
        reissue_packet_ref=ref("reissue", kind="scientist.reissue_packet"),
    )
    try:
        assert_decision_grade_exports_consistent(exports.values())
    except ValueError as exc:
        notes.append(f"decision_grade_exports_not_ref_consistent:{exc}")
    if set(exports) != set(OutputAudience):
        notes.append("decision_grade_exports_missing_audience")
    if "frontend_trust_view" not in exports[OutputAudience.MACHINE].payload:
        notes.append("machine_export_missing_frontend_trust_view")
    hidden_benchmark = exports[OutputAudience.PUBLIC].model_dump(mode="json")
    hidden_benchmark["payload"]["hidden_benchmark_ref"] = "hidden_holdout:answer"
    try:
        DecisionGradeExport.model_validate(hidden_benchmark)
    except ValidationError:
        pass
    else:
        notes.append("public_compiler_hidden_benchmark_ref_not_blocked")

    return not notes, notes


def _ref_payload(ref: _ArtifactRefLike) -> dict[str, str]:
    return {
        "artifact_id": str(ref.artifact_id),
        "kind": ref.kind,
        "media_type": ref.media_type,
    }


def _claim_changes_missing_from_replay_diff(
    *,
    changed_claim_ids: set[str],
    replay_changed_claim_ids: list[str],
) -> list[str]:
    explained = {
        item.split(":", 1)[1] if ":" in item else item for item in replay_changed_claim_ids
    }
    return sorted(changed_claim_ids - explained)


def _shadow_evidence_notes(repo_root: Path) -> list[str]:
    path = repo_root / ACCEPTANCE_DOC
    if not path.is_file():
        return ["shadow_evidence_doc_missing"]
    text = _read_text(path)
    notes: list[str] = []
    if "shadow_evidence_status: measured" not in text:
        notes.append("shadow_evidence_status_not_measured")
    if not SHADOW_EVIDENCE_RE.search(text):
        notes.append("shadow_evidence_metric_missing")
    lowered = text.lower()
    if "residual risks" not in lowered:
        notes.append("shadow_evidence_residual_risks_missing")
    return notes


def _migration_doc_notes(repo_root: Path) -> list[str]:
    path = repo_root / MIGRATION_DOC
    if not path.is_file():
        return ["migration_doc_missing"]
    text = _read_text(path)
    notes = [
        f"unresolved_migration_token:{token}"
        for token in UNRESOLVED_MIGRATION_TOKENS
        if token in text
    ]
    notes.extend(
        _missing_tokens(repo_root, MIGRATION_DOC, MIGRATION_TOKENS, "missing_migration_token")
    )
    return notes


def _build_payload(repo_root: Path) -> dict[str, Any]:
    notes: list[str] = []
    missing_files = [str(path) for path in REQUIRED_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_file:{path}" for path in missing_files)

    wave1_ok, wave1_payload, wave1_notes = _run_wave1_gate(repo_root)
    notes.extend(wave1_notes)
    phase_gates_ok, phase_gate_reports, phase_gate_notes = _run_phase_gates(repo_root)
    notes.extend(phase_gate_notes)
    import_ok, import_notes = _import_and_validate(repo_root)
    notes.extend(import_notes)

    missing_acceptance_tokens = _missing_tokens(
        repo_root,
        ACCEPTANCE_DOC,
        ACCEPTANCE_TOKENS,
        "missing_acceptance_token",
    )
    notes.extend(missing_acceptance_tokens)
    missing_maturity_tokens = _missing_tokens(
        repo_root,
        MATURITY_DOC,
        MATURITY_TOKENS,
        "missing_maturity_token",
    )
    notes.extend(missing_maturity_tokens)
    migration_notes = _migration_doc_notes(repo_root)
    notes.extend(migration_notes)
    shadow_notes = _shadow_evidence_notes(repo_root)
    notes.extend(shadow_notes)
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
        (
            "best-in-class-wave2-acceptance.md",
            "best-in-class-maturity.md",
            "wave2-migration-notes.md",
            "check_scientist_best_in_class_wave2.py",
        ),
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
        "wave1_gate_green": wave1_ok,
        "phase_gates_green": phase_gates_ok,
        "cross_phase_invariants_validate": import_ok,
        "acceptance_doc_complete": not missing_acceptance_tokens,
        "maturity_doc_complete": not missing_maturity_tokens,
        "migration_notes_complete": not migration_notes,
        "shadow_evidence_complete": not shadow_notes,
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
        "wave1_gate_report": wave1_payload,
        "phase_gate_reports": phase_gate_reports,
        "notes": notes,
    }


def _result(payload: dict[str, Any]) -> ToolResult:
    status = "ok" if payload.get("passes_all") else "failed"
    note_list = list(payload.get("notes", []))
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=(
            "Scientist best-in-class Wave 2 is accepted"
            if status == "ok"
            else "Scientist best-in-class Wave 2 is incomplete"
        ),
        exit_code=0 if status == "ok" else 1,
        messages=tuple(
            ToolMessage(
                level="error" if status == "failed" else "info",
                message=str(note),
                rule_id="SCIENTIST_BEST_IN_CLASS_WAVE2",
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
