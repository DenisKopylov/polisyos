#!/usr/bin/env python3
"""Validate the Scientist best-in-class Phase 1.1 claim spine."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase1_1"
TOOL_NAME = "ci.check-scientist-best-in-class-phase1-1"

CLAIMS_PACKAGE = Path("src/polisyos/scientist/claims")
REFERENCE_DOC = Path("docs/reference/scientist/claims.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
REQUIRED_PACKAGE_FILES: tuple[Path, ...] = (
    CLAIMS_PACKAGE / "__init__.py",
    CLAIMS_PACKAGE / "models.py",
    CLAIMS_PACKAGE / "ledger.py",
    CLAIMS_PACKAGE / "readiness.py",
    CLAIMS_PACKAGE / "projections.py",
    CLAIMS_PACKAGE / "validators.py",
)
REQUIRED_TEST_FILES: tuple[Path, ...] = (
    Path("tests/unit/scientist/claims/test_models.py"),
    Path("tests/unit/scientist/claims/test_readiness.py"),
    Path("tests/unit/scientist/claims/test_ledger.py"),
    Path("tests/unit/scientist/claims/test_projections.py"),
    Path("tests/tools/test_scientist_best_in_class_phase1_1.py"),
)
REQUIRED_NEGATIVE_TEST_TOKENS: dict[Path, tuple[str, ...]] = {
    Path("tests/unit/scientist/nodes/test_decision_packet_node_v3.py"): (
        "claim_spine_validation_failed",
        "fail_on_naked_claims",
        "legacy_missing",
    ),
    Path("tests/unit/scientist/nodes/builtins/governance/test_run_governance_claims.py"): (
        "claim_spine.naked_decision_claims",
        "missing_claims_ref_for_decision_bearing_state",
    ),
    Path("tests/unit/scientist/claims/test_readiness.py"): (
        "test_legal_claim_without_evidence_requires_review",
    ),
    Path("tests/unit/scientist/claims/test_models.py"): (
        "test_claim_with_unresolved_counterevidence_cannot_be_publishable",
    ),
    Path("tests/unit/scientist/claims/test_projections.py"): ("legacy_claim_ledger_status",),
}
INTEGRATION_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py"),
    Path("src/polisyos/scientist/nodes/builtins/decide/build_policy_output_bundle.py"),
    Path("src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py"),
    Path("src/polisyos/scientist/governance/report.py"),
    Path("src/polisyos/scientist/governance/accountability.py"),
    Path("src/polisyos/scientist/causal/validity.py"),
    Path("src/polisyos/scientist/frontier_runtime.py"),
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _import_and_validate_claim_fixture(repo_root: Path) -> tuple[bool, list[str]]:
    notes: list[str] = []
    sys.path.insert(0, str(repo_root / "src"))
    try:
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.claims import (
            ClaimLedger,
            ClaimPublishability,
            ClaimRecord,
            ClaimSupportStatus,
            ClaimType,
        )
        from polisyos.scientist.search.readiness import DecisionReadiness
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return False, [f"claim_package_import_failed:{exc.__class__.__name__}:{exc}"]

    try:
        evidence_ref = ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind="scientist.test_evidence",
            media_type="application/json",
        )
        ClaimLedger(
            run_id="phase1_1_gate",
            claims=[
                ClaimRecord(
                    claim_id="claim_gate",
                    run_id="phase1_1_gate",
                    claim_type=ClaimType.FACTUAL,
                    text="The claim spine validates fixtures.",
                    support_status=ClaimSupportStatus.SUPPORTED,
                    publishability=ClaimPublishability.INTERNAL_ONLY,
                    readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
                    evidence_refs=[evidence_ref],
                )
            ],
            source_artifact_refs=[evidence_ref],
        )
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        notes.append(f"claim_ledger_fixture_validation_failed:{exc.__class__.__name__}:{exc}")
    return not notes, notes


def _build_payload(repo_root: Path) -> dict[str, object]:
    notes: list[str] = []
    missing_package_files = [
        str(path) for path in REQUIRED_PACKAGE_FILES if not (repo_root / path).is_file()
    ]
    missing_tests = [str(path) for path in REQUIRED_TEST_FILES if not (repo_root / path).is_file()]
    missing_integrations = [
        str(path) for path in INTEGRATION_FILES if not (repo_root / path).is_file()
    ]
    notes.extend(f"missing_package_file:{path}" for path in missing_package_files)
    notes.extend(f"missing_test_file:{path}" for path in missing_tests)
    notes.extend(f"missing_integration_file:{path}" for path in missing_integrations)

    missing_negative_test_tokens: list[str] = []
    for path, tokens in REQUIRED_NEGATIVE_TEST_TOKENS.items():
        absolute = repo_root / path
        if not absolute.is_file():
            missing_negative_test_tokens.append(f"{path}:<file>")
            continue
        text = _read_text(absolute)
        missing_negative_test_tokens.extend(
            f"{path}:{token}" for token in tokens if token not in text
        )
    notes.extend(
        f"missing_required_negative_test_token:{token}" for token in missing_negative_test_tokens
    )

    import_ok, import_notes = _import_and_validate_claim_fixture(repo_root)
    notes.extend(import_notes)

    reference_exists = (repo_root / REFERENCE_DOC).is_file()
    if not reference_exists:
        notes.append(f"missing_reference_doc:{REFERENCE_DOC}")
    reference_tokens = (
        "Decision-bearing surface inventory",
        "ClaimRecord",
        "ClaimLedger",
        "claims_ref",
        "No naked claims",
    )
    missing_reference_tokens = [
        token for token in reference_tokens if not _contains(repo_root / REFERENCE_DOC, token)
    ]
    notes.extend(f"missing_reference_token:{token}" for token in missing_reference_tokens)

    missing_integration_tokens: list[str] = []
    for path in INTEGRATION_FILES:
        absolute = repo_root / path
        if not absolute.is_file():
            continue
        text = _read_text(absolute)
        if "claims_ref" not in text and "claim_projection" not in text:
            missing_integration_tokens.append(str(path))
    notes.extend(
        f"missing_claim_projection_integration:{path}" for path in missing_integration_tokens
    )

    claims_readiness_text = _read_text(repo_root / (CLAIMS_PACKAGE / "readiness.py"))
    readiness_redefined = "class DecisionReadiness" in claims_readiness_text
    if readiness_redefined:
        notes.append("claims_package_redefines_decision_readiness")

    active_plan_tokens = ("Phase 1.1", "Claim/Evidence/Readiness spine", "closed")
    active_plan_missing = [
        token for token in active_plan_tokens if not _contains(repo_root / ACTIVE_PLAN_DOC, token)
    ]
    notes.extend(f"missing_active_plan_token:{token}" for token in active_plan_missing)

    category_results = {
        "package_files_exist": not missing_package_files,
        "claim_package_imports": import_ok,
        "claim_ledger_fixture_validates": import_ok and not import_notes,
        "reference_doc_complete": reference_exists and not missing_reference_tokens,
        "tests_present": not missing_tests,
        "negative_tests_cover_required_cases": not missing_negative_test_tokens,
        "integration_targets_project_claims": not missing_integrations
        and not missing_integration_tokens,
        "decision_readiness_compatibility": not readiness_redefined,
        "active_plan_updated": not active_plan_missing,
    }
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "required_package_files": [str(path) for path in REQUIRED_PACKAGE_FILES],
        "required_test_files": [str(path) for path in REQUIRED_TEST_FILES],
        "required_negative_test_tokens": {
            str(path): list(tokens) for path, tokens in REQUIRED_NEGATIVE_TEST_TOKENS.items()
        },
        "integration_files": [str(path) for path in INTEGRATION_FILES],
        "notes": notes,
    }


def _phase1_1_result(payload: dict[str, object]) -> ToolResult:
    notes = payload.get("notes")
    note_list = list(notes) if isinstance(notes, list) else []
    status = "ok" if payload.get("passes_all") else "failed"
    summary = (
        "Scientist best-in-class Phase 1.1 claim spine is complete"
        if status == "ok"
        else "Scientist best-in-class Phase 1.1 claim spine is incomplete"
    )
    messages = tuple(
        ToolMessage(
            level="error" if status == "failed" else "info",
            message=str(note),
            rule_id="SCIENTIST_BEST_IN_CLASS_PHASE1_1",
        )
        for note in note_list
    )
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=summary,
        exit_code=0 if status == "ok" else 1,
        messages=messages,
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
    result = _phase1_1_result(payload)

    rendered = (
        json.dumps(payload, indent=2, sort_keys=True)
        if args.output_format == "json"
        else format_tool_result(result)
    )
    if args.output is not None:
        atomic_write_text(args.output, rendered + "\n")
    else:
        print(rendered)

    if args.require_passing and not payload["passes_all"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
