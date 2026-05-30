#!/usr/bin/env python3
"""Validate Scientist best-in-class Phase 2.3 VOI scheduler readiness."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase2_3"
TOOL_NAME = "ci.check-scientist-best-in-class-phase2-3"

REFERENCE_DOC = Path("docs/reference/scientist/voi-scheduler.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
READINESS_DOC = Path("docs/reference/scientist/best-in-class-readiness.md")
INVENTORY_DOC = Path("docs/reference/scientist/scientist-capability-inventory.md")
SCIENTIST_INDEX_DOC = Path("docs/reference/scientist/index.md")
WAVE2_CONTRACT_DOC = Path("docs/reference/scientist/wave2-runtime-contracts.md")
MKDOCS_CONFIG = Path("architecture/tooling/mkdocs/generated.yml")

REQUIRED_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/methods/search/voi_models.py"),
    Path("src/polisyos/scientist/methods/search/voi_scheduler.py"),
    Path("src/polisyos/scientist/methods/search/voi_calibration.py"),
    Path("src/polisyos/scientist/governance/human_review/voi_escalation.py"),
    Path("src/polisyos/scientist/evidence/claim_support.py"),
    Path("src/polisyos/scientist/nodes/builtins/state_keys.py"),
    Path("src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py"),
    Path("src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py"),
    REFERENCE_DOC,
    Path("tools/ci/check_scientist_best_in_class_phase2_3.py"),
    Path("tests/unit/scientist/search/test_voi_models.py"),
    Path("tests/unit/scientist/search/test_voi_reports.py"),
    Path("tests/unit/scientist/search/test_voi_calibration.py"),
    Path("tests/unit/scientist/evidence/test_claim_support_voi.py"),
    Path("tests/unit/scientist/governance/human_review/test_voi_escalation.py"),
    Path("tests/repo_quality/tools/test_scientist_best_in_class_phase2_3.py"),
)
REFERENCE_TOKENS: tuple[str, ...] = (
    "VOIDecisionRecord",
    "VOIRunReport",
    "VOIShadowBaselineComparison",
    "benchmark authority evidence",
    "required human review",
    "governance publication blocks",
    "Claim Ledger evidence",
    "calibration and regret refs",
    "voi_run_report_ref",
)
PLAN_TOKENS: tuple[str, ...] = (
    "Фаза 2.3 - VOI scheduler",
    "closed",
    "check_scientist_best_in_class_phase2_3.py",
)
READINESS_TOKENS: tuple[str, ...] = (
    "Phase 2.3 - VOI scheduler",
    "voi-scheduler.md",
    "check_scientist_best_in_class_phase2_3.py",
    "closed",
)
INDEX_TOKENS: tuple[str, ...] = ("voi-scheduler.md", "VOI scheduler")
MKDOCS_TOKENS: tuple[str, ...] = ("reference/scientist/voi-scheduler.md",)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _missing_tokens(repo_root: Path, path: Path, tokens: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}:{token}" for token in tokens if not _contains(repo_root / path, token)]


def _run_phase2_2_gate(repo_root: Path) -> tuple[bool, dict[str, Any], list[str]]:
    try:
        module = importlib.import_module("tools.ci.check_scientist_best_in_class_phase2_2")
    except Exception as exc:  # pragma: no cover - surfaced in payload.
        return (
            False,
            {"passes_all": False},
            [f"phase2_2_gate_import_failed:{exc.__class__.__name__}:{exc}"],
        )
    with TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "phase2_2.json"
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
                [f"phase2_2_gate_run_failed:{exc.__class__.__name__}:{exc}"],
            )
    notes: list[str] = []
    if exit_code != 0 or payload.get("passes_all") is not True:
        notes.append("phase2_2_gate_failed")
        notes.extend(f"phase2_2:{note}" for note in payload.get("notes", []))
    return not notes, payload, notes


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    notes: list[str] = []
    try:
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
        from polisyos.scientist.governance.human_review.models import ReviewRiskTier
        from polisyos.scientist.governance.human_review.oversight_policy import HumanReviewRequirement
        from polisyos.scientist.governance.human_review.voi_escalation import (
            build_human_escalation_voi_decision,
            validate_human_escalation_voi_decision,
        )
        from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_VOI_RUN_REPORT_REF
        from polisyos.scientist.methods.search.funnel.types import CheapSignalVector, FunnelStageResult
        from polisyos.scientist.methods.search.uncertainty import UncertaintyEnvelope
        from polisyos.scientist.methods.search.voi_calibration import (
            build_voi_calibration_report,
            compare_voi_to_static_baseline,
            validate_voi_default_enable,
        )
        from polisyos.scientist.methods.search.voi_models import (
            VOIDecisionRecord,
            VOIDecisionType,
            VOIRunReport,
        )
        from polisyos.scientist.methods.search.voi_scheduler import (
            SimpleVOIScheduler,
            build_adversarial_challenge_voi_decision,
            build_stop_search_voi_decision,
        )
    except Exception as exc:  # pragma: no cover - surfaced in payload.
        return False, [f"phase2_3_import_failed:{exc.__class__.__name__}:{exc}"]

    budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.0"))})
    cheap_signal = CheapSignalVector(
        expected_value_proxy=1.2,
        expected_information_gain=0.4,
    )
    result = FunnelStageResult(
        policy_candidate={},
        objective_value=0.0,
        is_promising=True,
        stage_name="L2",
        feedback={},
        uncertainty_envelope=UncertaintyEnvelope.unknown(),
        cheap_signal=cheap_signal,
        fidelity_level=2,
    )
    ticket = type(
        "Ticket",
        (),
        {"candidate_hash": "candidate_a", "next_level": 3, "last_result": result},
    )()
    scheduler = SimpleVOIScheduler(stage_costs={3: Decimal("0.25")})
    scheduling_decision = scheduler.prioritize([ticket], budget)[0]
    report = scheduler.report_for_decisions(
        run_id="run_voi",
        decisions=[scheduling_decision],
        calibration_status="shadow",
    )
    if not report.decisions:
        notes.append("scheduler_report_missing_decisions")
    if report.decisions[0].decision_type is not VOIDecisionType.CANDIDATE_EVALUATION:
        notes.append("scheduler_record_wrong_decision_type")
    if ARTIFACT_VOI_RUN_REPORT_REF != "voi_run_report_ref":
        notes.append("voi_run_report_state_key_missing")
    stop = build_stop_search_voi_decision(
        run_id="run_voi",
        marginal_expected_improvement=0.01,
        expected_cost_to_continue=0.1,
    )
    if stop.recommended_action != "stop_search":
        notes.append("stop_search_fixture_not_blocked_by_negative_voi")
    challenge = build_adversarial_challenge_voi_decision(
        run_id="run_voi",
        candidate_id="candidate_near_frontier",
        promotion_likelihood=0.8,
        impact_score=0.8,
        expected_challenge_cost=0.1,
    )
    if challenge.recommended_action != "run_adversarial_challenge":
        notes.append("adversarial_challenge_fixture_not_recommended")

    try:
        VOIDecisionRecord(
            decision_id="bad_gate",
            run_id="run_voi",
            decision_type=VOIDecisionType.CANDIDATE_EVALUATION,
            recommended_action="advance",
            expected_value=1.0,
            expected_cost=0.0,
            expected_risk_reduction=0.0,
            mandatory_gate_overrides=["benchmark_authority_missing"],
            explanation="Invalidly advance through a mandatory gate.",
        )
    except ValueError:
        pass
    else:
        notes.append("mandatory_gate_override_fixture_not_blocked")

    comparison = compare_voi_to_static_baseline(
        report,
        static_expected_cost=1.0,
        static_safety_score=0.95,
        voi_safety_score=0.96,
    )
    calibration = build_voi_calibration_report(report, comparison=comparison)
    if comparison.regret != 0.0 or not comparison.non_worse_safety:
        notes.append("calibration_fixture_not_non_worse")
    missing_default_refs = validate_voi_default_enable(
        report=report,
        calibration_report=calibration,
        calibration_report_ref=None,
        regret_report_ref=None,
    )
    if "missing_calibration_report_ref" not in missing_default_refs:
        notes.append("default_enable_missing_calibration_ref_not_blocked")
    if "missing_regret_report_ref" not in missing_default_refs:
        notes.append("default_enable_missing_regret_ref_not_blocked")

    requirement = HumanReviewRequirement(
        required=True,
        risk_tier=ReviewRiskTier.PUBLIC_SECTOR_HIGH,
        reasons=["high_risk_public_sector"],
        required_reviewer_count=2,
    )
    escalation = build_human_escalation_voi_decision(
        run_id="run_voi",
        requirement=requirement,
        expected_harm=2.0,
        reversal_risk=0.5,
    )
    if validate_human_escalation_voi_decision(escalation, requirement=requirement):
        notes.append("required_human_review_escalation_failed")

    VOIRunReport.model_validate(report.model_dump(mode="python"))
    ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="scientist.voi_calibration",
        media_type="application/json",
    )
    return not notes, notes


def _build_payload(repo_root: Path) -> dict[str, Any]:
    notes: list[str] = []
    missing_files = [str(path) for path in REQUIRED_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_file:{path}" for path in missing_files)

    phase2_2_ok, phase2_2_payload, phase2_2_notes = _run_phase2_2_gate(repo_root)
    notes.extend(phase2_2_notes)
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
        ("voi-scheduler.md", "check_scientist_best_in_class_phase2_3.py"),
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
        ("Phase 2.3 - VOI scheduler", "closed"),
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
        "phase2_2_gate_green": phase2_2_ok,
        "voi_contracts_validate": import_ok,
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
        "phase2_2_gate_report": phase2_2_payload,
        "notes": notes,
    }


def _result(payload: dict[str, Any]) -> ToolResult:
    status = "ok" if payload.get("passes_all") else "failed"
    note_list = list(payload.get("notes", []))
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=(
            "Scientist best-in-class Phase 2.3 is accepted"
            if status == "ok"
            else "Scientist best-in-class Phase 2.3 is incomplete"
        ),
        exit_code=0 if status == "ok" else 1,
        messages=tuple(
            ToolMessage(
                level="error" if status == "failed" else "info",
                message=str(note),
                rule_id="SCIENTIST_BEST_IN_CLASS_PHASE2_3",
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
