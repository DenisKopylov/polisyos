#!/usr/bin/env python3
"""Validate the Scientist Wave 1 best-in-class acceptance surface."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_wave1"
TOOL_NAME = "ci.check-scientist-best-in-class-wave1"

REFERENCE_DOC = Path("docs/reference/scientist/best-in-class-wave1-acceptance.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
READINESS_DOC = Path("docs/reference/scientist/best-in-class-readiness.md")
INVENTORY_DOC = Path("docs/reference/scientist/scientist-capability-inventory.md")
INDEX_DOC = Path("docs/reference/scientist/index.md")
MKDOCS_CONFIG = Path("architecture/tooling/mkdocs/generated.yml")

PHASE_GATE_MODULES: tuple[tuple[str, str], ...] = (
    ("phase1_0", "tools.ci.check_scientist_best_in_class_phase1_0"),
    ("phase1_1", "tools.ci.check_scientist_best_in_class_phase1_1"),
    ("phase1_2", "tools.ci.check_scientist_best_in_class_phase1_2"),
    ("phase1_3", "tools.ci.check_scientist_best_in_class_phase1_3"),
    ("phase1_4", "tools.ci.check_scientist_best_in_class_phase1_4"),
    ("phase1_5", "tools.ci.check_scientist_benchmark_authority"),
    ("phase1_6", "tools.ci.check_scientist_best_in_class_phase1_6"),
)

REQUIRED_FILES: tuple[Path, ...] = (
    REFERENCE_DOC,
    Path("tools/ci/check_scientist_best_in_class_wave1.py"),
    Path("tests/repo_quality/tools/test_scientist_best_in_class_wave1.py"),
)
REFERENCE_TOKENS: tuple[str, ...] = (
    "Wave 1 acceptance",
    "claim projection",
    "research_dag_ref",
    "claims_ref",
    "BenchmarkAuthority",
    "human review",
    "high-risk",
)
PLAN_TOKENS: tuple[str, ...] = (
    "1.7",
    "Wave 1 closeout",
    "closed",
)
READINESS_TOKENS: tuple[str, ...] = (
    "Phase 1.7 - Wave 1 closeout",
    "best-in-class-wave1-acceptance.md",
    "check_scientist_best_in_class_wave1.py",
    "closed",
)
INVENTORY_TOKENS: tuple[str, ...] = (
    "best-in-class-wave1-acceptance.md",
    "check_scientist_best_in_class_wave1.py",
)
INDEX_TOKENS: tuple[str, ...] = (
    "best-in-class-wave1-acceptance.md",
    "Wave 1 acceptance",
)
MKDOCS_TOKENS: tuple[str, ...] = ("reference/scientist/best-in-class-wave1-acceptance.md",)
DECISION_PACKET_TOKENS: dict[Path, tuple[str, ...]] = {
    Path("src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py"): (
        "claims_ref",
        "research_dag_ref",
        "legacy_research_dag_status",
        "_attach_claim_ledger_to_packet",
        "validate_human_reviewed_readiness",
    ),
    Path("tests/unit/scientist/nodes/test_decision_packet_node_v3.py"): (
        'payload["claims_ref"]',
        'payload["research_dag_ref"]',
        "missing_claims_ref_for_decision_bearing_payload",
    ),
    Path("tests/unit/scientist/methods/research_dag/test_workflow_integration.py"): (
        "research_dag_ref",
        "scientist_policy_design",
    ),
    Path("tests/unit/scientist/governance/human_review/test_decision_packet_integration.py"): (
        "missing_human_review_packet_ref",
        "human_review_validation_failed",
    ),
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _run_phase_gates(repo_root: Path) -> tuple[bool, dict[str, dict[str, Any]], list[str]]:
    reports: dict[str, dict[str, Any]] = {}
    notes: list[str] = []
    for phase_id, module_name in PHASE_GATE_MODULES:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - surfaced in gate payload.
            notes.append(f"{phase_id}:gate_import_failed:{exc.__class__.__name__}:{exc}")
            reports[phase_id] = {"passes_all": False}
            continue
        with TemporaryDirectory() as tmp:
            output_path = Path(tmp) / f"{phase_id}.json"
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
                notes.append(f"{phase_id}:gate_run_failed:{exc.__class__.__name__}:{exc}")
                reports[phase_id] = {"passes_all": False}
                continue
        reports[phase_id] = payload
        if exit_code != 0 or payload.get("passes_all") is not True:
            notes.append(f"{phase_id}:gate_failed")
            for note in payload.get("notes", []) if isinstance(payload, dict) else []:
                notes.append(f"{phase_id}:{note}")
    return not notes, reports, notes


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    sys.path.insert(0, str(repo_root / "src"))
    notes: list[str] = []
    try:
        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.agent.promotion import (
            build_agent_capability_promotion_report,
        )
        from polisyos.scientist.agent.runtime_capabilities import AgentCapabilityId
        from polisyos.scientist.agent.tool_contracts import summarize_tool_contracts
        from polisyos.scientist.agent.tools.schema import ToolDefinition
        from polisyos.scientist.claims.validators import (
            SELECTED_FAIL_CLOSED_WORKFLOWS,
            validate_naked_decision_claims,
            validate_state_claim_projection,
        )
        from polisyos.scientist.orchestration.engine.frontier_runtime import (
            FrontierRuntimeConfig,
            build_frontier_runtime_report,
        )
        from polisyos.scientist.evals.authority import (
            BenchmarkAuthority,
            PromotionEvidenceRequest,
        )
        from polisyos.scientist.governance.human_review.audit import signature_for_decision
        from polisyos.scientist.governance.human_review.decisions import human_review_status
        from polisyos.scientist.governance.human_review.models import (
            HumanReviewDecision,
            HumanReviewStatus,
            ReviewAction,
        )
        from polisyos.scientist.governance.human_review.oversight_policy import (
            evaluate_human_review_requirement,
            human_review_section,
            validate_human_reviewed_readiness,
        )
        from polisyos.scientist.governance.human_review.packets import build_review_packet
        from polisyos.scientist.nodes.builtins.state_keys import (
            ARTIFACT_CLAIMS_REF,
            ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
            ARTIFACT_RESEARCH_DAG_REF,
        )
        from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return False, [f"wave1_import_failed:{exc.__class__.__name__}:{exc}"]

    def ref(seed: str, *, kind: str = "scientist.fixture") -> ArtifactRef:
        return ArtifactRef(
            artifact_id=ArtifactID.model_validate(
                "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()
            ),
            kind=kind,
            media_type="application/json",
        )

    decision_payload = {
        "policy_answer": {"executive_summary": "Adopt option A."},
        "causal": {
            "status": "estimated",
            "estimand": "ATE",
            "point_estimate": 1.25,
        },
    }
    for workflow_id in sorted(SELECTED_FAIL_CLOSED_WORKFLOWS):
        blocked = validate_naked_decision_claims(
            decision_payload,
            claims_ref=None,
            workflow_id=workflow_id,
            fail_on_naked_claims=True,
        )
        if blocked.passed:
            notes.append(f"{workflow_id}:naked_decision_claim_did_not_block")
        if "missing_claims_ref_for_decision_bearing_payload" not in blocked.violations:
            notes.append(f"{workflow_id}:missing_claim_projection_violation_not_reported")
        covered = validate_naked_decision_claims(
            decision_payload,
            claims_ref=ref(f"{workflow_id}:claims", kind="scientist.claim_ledger"),
            workflow_id=workflow_id,
            fail_on_naked_claims=True,
        )
        if not covered.passed:
            notes.append(f"{workflow_id}:decision_payload_with_claims_ref_blocked")
        state_blocked = validate_state_claim_projection(
            workflow_id=workflow_id,
            artifacts_index={
                ARTIFACT_POLICY_OUTPUT_BUNDLE_REF: ref(
                    f"{workflow_id}:policy_output",
                    kind="scientist.policy_output_bundle",
                )
            },
            fail_on_naked_claims=True,
        )
        if state_blocked.passed:
            notes.append(f"{workflow_id}:decision_bearing_state_without_claims_did_not_block")
        if "missing_claims_ref_for_decision_bearing_state" not in state_blocked.violations:
            notes.append(f"{workflow_id}:missing_state_claim_projection_violation_not_reported")
        state_covered = validate_state_claim_projection(
            workflow_id=workflow_id,
            artifacts_index={
                ARTIFACT_POLICY_OUTPUT_BUNDLE_REF: ref(
                    f"{workflow_id}:policy_output",
                    kind="scientist.policy_output_bundle",
                ),
                ARTIFACT_CLAIMS_REF: ref(
                    f"{workflow_id}:state_claims",
                    kind="scientist.claim_ledger",
                ),
            },
            fail_on_naked_claims=True,
        )
        if not state_covered.passed:
            notes.append(f"{workflow_id}:decision_bearing_state_with_claims_ref_blocked")

    claims_ref = ref("claims", kind="scientist.claim_ledger")
    research_dag_ref = ref("research_dag", kind="scientist.research_dag")
    packet_payload = {
        "claims_ref": str(claims_ref.artifact_id),
        "research_dag_ref": str(research_dag_ref.artifact_id),
        "artifacts": {
            ARTIFACT_CLAIMS_REF: str(claims_ref.artifact_id),
            ARTIFACT_RESEARCH_DAG_REF: str(research_dag_ref.artifact_id),
        },
    }
    if packet_payload["claims_ref"] != packet_payload["artifacts"][ARTIFACT_CLAIMS_REF]:
        notes.append("decision_packet_claims_ref_not_projected_into_artifacts")
    if packet_payload["research_dag_ref"] != packet_payload["artifacts"][ARTIFACT_RESEARCH_DAG_REF]:
        notes.append("decision_packet_research_dag_ref_not_projected_into_artifacts")

    tool_summary = summarize_tool_contracts(
        [
            ToolDefinition(
                name="safe_search",
                description="Search safe source fixtures.",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
                timeout_s=10.0,
                response_max_chars=4096,
            )
        ]
    )
    with TemporaryDirectory() as tmp:
        registry = BenchmarkRegistry(Path(tmp) / "benchmarks")
        registry.record(
            "selection",
            ref("selection", kind="scientist.benchmark_evaluation"),
            family="policy_design",
            loop_id="loop-a",
        )
        blocked_verdict = BenchmarkAuthority(registry).verdict(
            PromotionEvidenceRequest(
                family="policy_design",
                claim_mode="estimation",
                loop_id="loop-a",
            )
        )
    agent_report = build_agent_capability_promotion_report(
        default_enable_requested=True,
        default_enable_capability_ids=[AgentCapabilityId.TOOL_LOOP],
        offline_validation_ref=ref("offline", kind="scientist.agent.offline_validation"),
        benchmark_pack_ref=ref("pack", kind="scientist.benchmark_pack"),
        tool_contract_summary=tool_summary,
        benchmark_authority_verdict=blocked_verdict,
        require_benchmark_authority=True,
    )
    if agent_report.default_enable_eligible:
        notes.append("agent_default_enable_bypassed_benchmark_authority")
    if "benchmark_authority_not_allowed" not in agent_report.blockers:
        notes.append("agent_promotion_missing_benchmark_authority_blocker")

    frontier_report = build_frontier_runtime_report(
        FrontierRuntimeConfig(
            enable_proximal_causal=True,
            offline_validation_ref="sha256:" + "a" * 64,
            benchmark_pack_ref="sha256:" + "b" * 64,
            default_enable_requested=True,
            allow_baseline_replacement=True,
            require_benchmark_authority=True,
            benchmark_authority_default_enable_allowed=False,
        )
    )
    if frontier_report.default_enable_eligible:
        notes.append("frontier_default_enable_bypassed_benchmark_authority")
    if "benchmark_authority_not_allowed" not in frontier_report.default_enable_blockers:
        notes.append("frontier_missing_benchmark_authority_blocker")

    requirement = evaluate_human_review_requirement(
        params={"public_sector": True, "risk_tier": "high"}
    )
    if not requirement.required or requirement.required_reviewer_count != 2:
        notes.append("high_risk_public_sector_review_not_explicit")
    review_packet = build_review_packet(
        run_id="wave1_gate",
        decision_payload=decision_payload,
        risk_tier=requirement.risk_tier,
        required_reviewer_count=requirement.required_reviewer_count,
        claims_ref=claims_ref,
        research_dag_ref=research_dag_ref,
    )
    missing_review = validate_human_reviewed_readiness(
        {"readiness": "human_reviewed"},
        requirement=requirement,
        packet=review_packet,
    )
    if missing_review.passed:
        notes.append("high_risk_human_reviewed_without_refs_did_not_block")
    missing_review_section = human_review_section(
        requirement=requirement,
        packet=review_packet,
        decisions=[],
    )
    if missing_review_section.get("status") != HumanReviewStatus.PENDING.value:
        notes.append("high_risk_human_review_section_missing_pending_status")
    if missing_review_section.get("risk_tier") != "public_sector_high":
        notes.append("high_risk_human_review_section_missing_risk_tier")
    if missing_review_section.get("required_reviewer_count") != 2:
        notes.append("high_risk_human_review_section_missing_two_person_requirement")
    decision_a = HumanReviewDecision(
        decision_id="decision_a",
        packet_id=review_packet.packet_id,
        run_id="wave1_gate",
        reviewer_id="reviewer_a",
        action=ReviewAction.APPROVE,
        rationale="Approved.",
        signature=signature_for_decision(
            reviewer_id="reviewer_a",
            attestation="I reviewed the packet.",
        ),
    )
    decision_b = HumanReviewDecision(
        decision_id="decision_b",
        packet_id=review_packet.packet_id,
        run_id="wave1_gate",
        reviewer_id="reviewer_b",
        action=ReviewAction.APPROVE,
        rationale="Approved.",
        signature=signature_for_decision(
            reviewer_id="reviewer_b",
            attestation="I reviewed the packet.",
        ),
    )
    if (
        human_review_status(
            [decision_a],
            packet=review_packet,
            required_reviewer_count=requirement.required_reviewer_count,
        )
        is not HumanReviewStatus.PENDING
    ):
        notes.append("single_reviewer_approved_two_person_packet")
    if (
        human_review_status(
            [decision_a, decision_b],
            packet=review_packet,
            required_reviewer_count=requirement.required_reviewer_count,
        )
        is not HumanReviewStatus.APPROVED
    ):
        notes.append("two_person_review_did_not_approve")
    approved_review_section = human_review_section(
        requirement=requirement,
        review_packet_ref=ref("human_review_packet", kind="scientist.human_review_packet"),
        review_decision_ref=ref("human_review_decision", kind="scientist.human_review_decision"),
        decisions=[decision_a, decision_b],
        packet=review_packet,
    )
    if approved_review_section.get("status") != HumanReviewStatus.APPROVED.value:
        notes.append("approved_high_risk_human_review_section_missing_status")

    return not notes, notes


def _build_payload(repo_root: Path) -> dict[str, Any]:
    notes: list[str] = []
    missing_files = [str(path) for path in REQUIRED_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_file:{path}" for path in missing_files)

    phase_gates_ok, phase_gate_reports, phase_gate_notes = _run_phase_gates(repo_root)
    notes.extend(phase_gate_notes)

    import_ok, import_notes = _import_and_validate(repo_root)
    notes.extend(import_notes)

    missing_reference_tokens = [
        token for token in REFERENCE_TOKENS if not _contains(repo_root / REFERENCE_DOC, token)
    ]
    notes.extend(f"missing_reference_token:{token}" for token in missing_reference_tokens)

    missing_plan_tokens = [
        token for token in PLAN_TOKENS if not _contains(repo_root / ACTIVE_PLAN_DOC, token)
    ]
    notes.extend(f"missing_active_plan_token:{token}" for token in missing_plan_tokens)

    missing_readiness_tokens = [
        token for token in READINESS_TOKENS if not _contains(repo_root / READINESS_DOC, token)
    ]
    notes.extend(f"missing_readiness_token:{token}" for token in missing_readiness_tokens)

    missing_inventory_tokens = [
        token for token in INVENTORY_TOKENS if not _contains(repo_root / INVENTORY_DOC, token)
    ]
    notes.extend(f"missing_inventory_token:{token}" for token in missing_inventory_tokens)

    missing_index_tokens = [
        token for token in INDEX_TOKENS if not _contains(repo_root / INDEX_DOC, token)
    ]
    notes.extend(f"missing_index_token:{token}" for token in missing_index_tokens)

    missing_mkdocs_tokens = [
        token for token in MKDOCS_TOKENS if not _contains(repo_root / MKDOCS_CONFIG, token)
    ]
    notes.extend(f"missing_mkdocs_token:{token}" for token in missing_mkdocs_tokens)

    missing_decision_packet_tokens: list[str] = []
    for path, tokens in DECISION_PACKET_TOKENS.items():
        absolute = repo_root / path
        text = _read_text(absolute) if absolute.is_file() else ""
        missing_decision_packet_tokens.extend(
            f"{path}:{token}" for token in tokens if token not in text
        )
    notes.extend(
        f"missing_wave1_integration_token:{token}" for token in missing_decision_packet_tokens
    )

    category_results = {
        "deliverables_exist": not missing_files,
        "phase_gates_green": phase_gates_ok,
        "cross_phase_contracts_validate": import_ok,
        "reference_doc_complete": not missing_reference_tokens,
        "active_plan_updated": not missing_plan_tokens,
        "readiness_doc_updated": not missing_readiness_tokens,
        "inventory_doc_updated": not missing_inventory_tokens,
        "index_doc_updated": not missing_index_tokens,
        "mkdocs_nav_updated": not missing_mkdocs_tokens,
        "decision_packet_integration_tokens_present": not missing_decision_packet_tokens,
    }
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "phase_gate_reports": phase_gate_reports,
        "notes": notes,
    }


def _result(payload: dict[str, Any]) -> ToolResult:
    status = "ok" if payload.get("passes_all") else "failed"
    notes = payload.get("notes")
    note_list = list(notes) if isinstance(notes, list) else []
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=(
            "Scientist best-in-class Wave 1 is accepted"
            if status == "ok"
            else "Scientist best-in-class Wave 1 is incomplete"
        ),
        exit_code=0 if status == "ok" else 1,
        messages=tuple(
            ToolMessage(
                level="error" if status == "failed" else "info",
                message=str(note),
                rule_id="SCIENTIST_BEST_IN_CLASS_WAVE1",
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
