#!/usr/bin/env python3
"""Validate the Scientist Phase 1.6 human oversight surface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase1_6"
TOOL_NAME = "ci.check-scientist-best-in-class-phase1-6"

REFERENCE_DOC = Path("docs/reference/scientist/human-oversight.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
REQUIRED_PACKAGE_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/governance/human_review/__init__.py"),
    Path("src/polisyos/scientist/governance/human_review/models.py"),
    Path("src/polisyos/scientist/governance/human_review/queue.py"),
    Path("src/polisyos/scientist/governance/human_review/decisions.py"),
    Path("src/polisyos/scientist/governance/human_review/packets.py"),
    Path("src/polisyos/scientist/governance/human_review/oversight_policy.py"),
    Path("src/polisyos/scientist/governance/human_review/audit.py"),
)
REQUIRED_INTEGRATION_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/governance/report.py"),
    Path("src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py"),
    Path("src/polisyos/scientist/nodes/builtins/governance/run_governance.py"),
    Path("src/polisyos/scientist/nodes/builtins/state_keys.py"),
)
REQUIRED_TEST_FILES: tuple[Path, ...] = (
    Path("tests/unit/scientist/governance/human_review/test_models.py"),
    Path("tests/unit/scientist/governance/human_review/test_persistence.py"),
    Path("tests/unit/scientist/governance/human_review/test_queue.py"),
    Path("tests/unit/scientist/governance/human_review/test_oversight_policy.py"),
    Path("tests/unit/scientist/governance/human_review/test_governance_integration.py"),
    Path("tests/unit/scientist/governance/human_review/test_decision_packet_integration.py"),
    Path("tests/repo_quality/tools/test_scientist_best_in_class_phase1_6.py"),
)
REFERENCE_TOKENS: tuple[str, ...] = (
    "HumanReviewPacket",
    "HumanReviewDecision",
    "HumanReviewQueueState",
    "FundamentalRightsChecklist",
    "human_review_packet_ref",
    "human_review_decision_ref",
    "human_reviewed",
)
INTEGRATION_TOKENS: dict[Path, tuple[str, ...]] = {
    Path("src/polisyos/scientist/governance/report.py"): (
        "human_review_packet_ref",
        "human_review_decision_ref",
    ),
    Path("src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py"): (
        "validate_human_reviewed_readiness",
        "human_review_validation_failed",
        "ARTIFACT_HUMAN_REVIEW_PACKET_REF",
        "ARTIFACT_HUMAN_REVIEW_DECISION_REF",
    ),
    Path("src/polisyos/scientist/nodes/builtins/state_keys.py"): (
        "ARTIFACT_HUMAN_REVIEW_PACKET_REF",
        "ARTIFACT_HUMAN_REVIEW_DECISION_REF",
    ),
}
NEGATIVE_TEST_TOKENS: dict[Path, tuple[str, ...]] = {
    Path("tests/unit/scientist/governance/human_review/test_models.py"): (
        "override_reason",
        "stop_release",
    ),
    Path("tests/unit/scientist/governance/human_review/test_oversight_policy.py"): (
        "human_reviewed_readiness_without_review_ref",
        "explanation_insufficient",
        "REQUEST_RERUN",
        "INTERRUPT_RELEASE",
    ),
    Path("tests/unit/scientist/governance/human_review/test_decision_packet_integration.py"): (
        "governance_human_gate",
        "missing_human_review_packet_ref",
        "human_review_validation_failed",
    ),
    Path("tests/unit/scientist/governance/human_review/test_governance_integration.py"): (
        "test_run_governance_includes_review_refs_from_state",
    ),
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    sys.path.insert(0, str(repo_root / "src"))
    notes: list[str] = []
    try:
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.scientist.governance.human_review.audit import signature_for_decision
        from polisyos.scientist.governance.human_review.decisions import (
            human_review_status,
            persist_review_decision,
        )
        from polisyos.scientist.governance.human_review.models import (
            HumanReviewDecision,
            HumanReviewStatus,
            ReviewAction,
        )
        from polisyos.scientist.governance.human_review.oversight_policy import (
            evaluate_human_review_requirement,
            validate_human_reviewed_readiness,
        )
        from polisyos.scientist.governance.human_review.packets import (
            build_review_packet,
            load_review_packet,
            persist_review_packet,
        )
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return False, [f"human_review_import_failed:{exc.__class__.__name__}:{exc}"]

    with TemporaryDirectory() as tmp:
        store = FileSystemCAS(Path(tmp) / "cas")
        packet = build_review_packet(
            run_id="gate_run",
            risk_tier="public_sector_high",
            required_reviewer_count=2,
        )
        packet_ref = persist_review_packet(store, packet)
        loaded_packet = load_review_packet(store, packet_ref)
        if loaded_packet.packet_id != packet.packet_id:
            notes.append("review_packet_roundtrip_failed")
        decision = HumanReviewDecision(
            decision_id="decision_gate",
            packet_id=packet.packet_id,
            run_id="gate_run",
            reviewer_id="reviewer_a",
            action=ReviewAction.APPROVE,
            rationale="Reviewed.",
            signature=signature_for_decision(
                reviewer_id="reviewer_a",
                attestation="I reviewed the packet.",
            ),
            packet_ref=packet_ref,
        )
        decision_ref = persist_review_decision(store, decision)
        if decision_ref.kind != "scientist.human_review_decision":
            notes.append("review_decision_kind_mismatch")
        if human_review_status([decision], packet=packet) is not HumanReviewStatus.PENDING:
            notes.append("two_person_status_did_not_remain_pending")
        requirement = evaluate_human_review_requirement(
            params={"public_sector": True, "risk_tier": "high"}
        )
        if not requirement.required or requirement.required_reviewer_count != 2:
            notes.append("public_sector_high_risk_requirement_failed")
        blocked = validate_human_reviewed_readiness({"readiness": "human_reviewed"})
        if blocked.passed:
            notes.append("human_reviewed_without_ref_did_not_block")
    return not notes, notes


def _build_payload(repo_root: Path) -> dict[str, object]:
    notes: list[str] = []
    missing_package_files = [
        str(path) for path in REQUIRED_PACKAGE_FILES if not (repo_root / path).is_file()
    ]
    missing_integration_files = [
        str(path) for path in REQUIRED_INTEGRATION_FILES if not (repo_root / path).is_file()
    ]
    missing_tests = [str(path) for path in REQUIRED_TEST_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_package_file:{path}" for path in missing_package_files)
    notes.extend(f"missing_integration_file:{path}" for path in missing_integration_files)
    notes.extend(f"missing_test_file:{path}" for path in missing_tests)

    import_ok, import_notes = _import_and_validate(repo_root)
    notes.extend(import_notes)

    missing_reference_tokens = [
        token for token in REFERENCE_TOKENS if not _contains(repo_root / REFERENCE_DOC, token)
    ]
    notes.extend(f"missing_reference_token:{token}" for token in missing_reference_tokens)

    missing_integration_tokens: list[str] = []
    for path, tokens in INTEGRATION_TOKENS.items():
        text = _read_text(repo_root / path) if (repo_root / path).is_file() else ""
        missing_integration_tokens.extend(
            f"{path}:{token}" for token in tokens if token not in text
        )
    notes.extend(f"missing_integration_token:{token}" for token in missing_integration_tokens)

    missing_negative_test_tokens: list[str] = []
    for path, tokens in NEGATIVE_TEST_TOKENS.items():
        text = _read_text(repo_root / path) if (repo_root / path).is_file() else ""
        missing_negative_test_tokens.extend(
            f"{path}:{token}" for token in tokens if token not in text
        )
    notes.extend(
        f"missing_required_negative_test_token:{token}" for token in missing_negative_test_tokens
    )

    active_plan_missing = [
        token
        for token in ("1.6", "Human oversight", "closed")
        if not _contains(repo_root / ACTIVE_PLAN_DOC, token)
    ]
    notes.extend(f"missing_active_plan_token:{token}" for token in active_plan_missing)

    category_results = {
        "package_files_exist": not missing_package_files,
        "integration_files_exist": not missing_integration_files,
        "tests_present": not missing_tests,
        "models_import_and_validate": import_ok,
        "reference_doc_complete": not missing_reference_tokens,
        "integration_tokens_present": not missing_integration_tokens,
        "negative_tests_cover_required_cases": not missing_negative_test_tokens,
        "active_plan_updated": not active_plan_missing,
    }
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "notes": notes,
    }


def _result(payload: dict[str, object]) -> ToolResult:
    status = "ok" if payload.get("passes_all") else "failed"
    notes = payload.get("notes")
    note_list = list(notes) if isinstance(notes, list) else []
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=(
            "Scientist human oversight Phase 1.6 is complete"
            if status == "ok"
            else "Scientist human oversight Phase 1.6 is incomplete"
        ),
        exit_code=0 if status == "ok" else 1,
        messages=tuple(
            ToolMessage(
                level="error" if status == "failed" else "info",
                message=str(note),
                rule_id="SCIENTIST_BEST_IN_CLASS_PHASE1_6",
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
