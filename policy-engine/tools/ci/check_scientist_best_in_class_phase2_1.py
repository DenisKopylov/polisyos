#!/usr/bin/env python3
"""Validate the Scientist best-in-class Phase 2.1 Claim Ledger surface."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase2_1"
TOOL_NAME = "ci.check-scientist-best-in-class-phase2-1"

REFERENCE_DOC = Path("docs/reference/scientist/claim-ledger.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
READINESS_DOC = Path("docs/reference/scientist/best-in-class-readiness.md")
INVENTORY_DOC = Path("docs/reference/scientist/scientist-capability-inventory.md")
SCIENTIST_INDEX_DOC = Path("docs/reference/scientist/index.md")
MKDOCS_CONFIG = Path("architecture/tooling/mkdocs/generated.yml")

REQUIRED_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/evidence/claims/lifecycle.py"),
    Path("src/polisyos/scientist/evidence/claims/audit.py"),
    Path("src/polisyos/scientist/evidence/claims/export.py"),
    Path("src/polisyos/scientist/evidence/claims/diff.py"),
    REFERENCE_DOC,
    Path("tools/ci/check_scientist_best_in_class_phase2_1.py"),
    Path("tests/unit/scientist/evidence/claims/test_lifecycle.py"),
    Path("tests/unit/scientist/evidence/claims/test_audit.py"),
    Path("tests/unit/scientist/evidence/claims/test_diff.py"),
    Path("tests/unit/scientist/evidence/claims/test_export.py"),
    Path("tests/repo_quality/tools/test_scientist_best_in_class_phase2_1.py"),
)
REFERENCE_TOKENS: tuple[str, ...] = (
    "AppendOnlyClaimLedger",
    "ClaimLifecycleEvent",
    "claim_ledger_summary",
    "blocked_claim_summary",
    "claim_ledger_v2_ref",
    "legacy_no_events",
    "Migration",
    "Rollback",
)
PLAN_TOKENS: tuple[str, ...] = (
    "Фаза 2.1 - Claim Ledger",
    "closed",
    "check_scientist_best_in_class_phase2_1.py",
)
READINESS_TOKENS: tuple[str, ...] = (
    "Phase 2.1 - Claim Ledger",
    "claim-ledger.md",
    "check_scientist_best_in_class_phase2_1.py",
    "closed",
)
INDEX_TOKENS: tuple[str, ...] = (
    "claim-ledger.md",
    "Claim Ledger",
)
MKDOCS_TOKENS: tuple[str, ...] = ("reference/scientist/claim-ledger.md",)
INTEGRATION_TOKENS: dict[Path, tuple[str, ...]] = {
    Path("src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py"): (
        "claim_ledger_summary",
        "blocked_claim_summary",
        "claim_ledger_v2_ref",
        "CLAIM_LEDGER_V2_FLAG",
    ),
    Path("src/polisyos/scientist/policy_design/output.py"): (
        "claim_ledger_summary",
        "blocked_claim_summary",
    ),
    Path("tests/unit/scientist/nodes/test_decision_packet_node_v3.py"): (
        'payload["claim_ledger_summary"]',
        'payload["blocked_claim_summary"]',
        'payload["claim_ledger_v2_ref"]',
    ),
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _run_phase2_0_gate(repo_root: Path) -> tuple[bool, dict[str, Any], list[str]]:
    try:
        module = importlib.import_module("tools.ci.check_scientist_best_in_class_phase2_0")
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return (
            False,
            {"passes_all": False},
            [f"phase2_0_gate_import_failed:{exc.__class__.__name__}:{exc}"],
        )
    with TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "phase2_0.json"
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
                [f"phase2_0_gate_run_failed:{exc.__class__.__name__}:{exc}"],
            )
    notes: list[str] = []
    if exit_code != 0 or payload.get("passes_all") is not True:
        notes.append("phase2_0_gate_failed")
        notes.extend(f"phase2_0:{note}" for note in payload.get("notes", []))
    return not notes, payload, notes


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    notes: list[str] = []
    try:
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.evidence.claims.diff import diff_claim_ledgers
        from polisyos.scientist.evidence.claims.export import (
            ClaimExportAudience,
            blocked_claim_summary,
            claim_ledger_summary,
            export_claim_ledger,
        )
        from polisyos.scientist.evidence.claims.lifecycle import (
            AppendOnlyClaimLedger,
            ClaimLifecycleAction,
            ClaimLifecycleEvent,
            build_initial_append_only_ledger,
            validate_claim_transition,
        )
        from polisyos.scientist.evidence.claims.models import (
            ClaimLedger,
            ClaimPublishability,
            ClaimRecord,
            ClaimSupportStatus,
            ClaimType,
        )
        from polisyos.scientist.search.readiness import DecisionReadiness
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return False, [f"phase2_1_import_failed:{exc.__class__.__name__}:{exc}"]

    def ref(seed: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id="sha256:" + seed * 64,
            kind="scientist.fixture",
            media_type="application/json",
        )

    before_claim = ClaimRecord(
        claim_id="claim_1",
        run_id="phase2_1",
        claim_type=ClaimType.FACTUAL,
        text="Claim one.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        evidence_refs=[ref("1")],
    )
    blocked_claim = before_claim.model_copy(
        update={
            "support_status": ClaimSupportStatus.CONTESTED,
            "publishability": ClaimPublishability.BLOCKED,
            "readiness_level": DecisionReadiness.ANALYST_ADVISORY,
            "counterevidence_refs": [ref("2")],
            "reviewer_refs": [ref("3")],
            "blocked_reasons": ["counterevidence_found"],
        }
    )
    before = ClaimLedger(run_id="phase2_1", claims=[before_claim])
    append_only = AppendOnlyClaimLedger(
        run_id="phase2_1",
        current_claims=[blocked_claim],
        events=[
            ClaimLifecycleEvent(
                event_id="event_blocked",
                claim_id="claim_1",
                run_id="phase2_1",
                action=ClaimLifecycleAction.BLOCKED,
                occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
                actor_id="reviewer",
                reason="Counterevidence found.",
            )
        ],
    )
    initialized = build_initial_append_only_ledger(
        before,
        actor_id="node",
        reason="Initial projection.",
        occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
    )
    if initialized.events[0].action is not ClaimLifecycleAction.CREATED:
        notes.append("initial_lifecycle_event_not_created")

    diff = diff_claim_ledgers(before, append_only)
    if diff.changed_support_claim_ids != ["claim_1"]:
        notes.append("diff_missing_changed_support")
    if diff.changed_readiness_claim_ids != ["claim_1"]:
        notes.append("diff_missing_changed_readiness")
    if diff.blocked_claim_ids != ["claim_1"]:
        notes.append("diff_missing_blocked_claim")
    reviewer_export = export_claim_ledger(
        append_only,
        audience=ClaimExportAudience.REVIEWER,
    )
    if not all(claim.visible for claim in reviewer_export.claims):
        notes.append("reviewer_export_hid_blocked_claim")
    if claim_ledger_summary(append_only).get("lifecycle_status") != "available":
        notes.append("ledger_summary_missing_lifecycle_status")
    if blocked_claim_summary(append_only).get("blocked_count") != 1:
        notes.append("blocked_summary_missing_blocked_claim")
    try:
        validate_claim_transition(
            before_claim,
            blocked_claim,
            action=ClaimLifecycleAction.UPDATED_SUPPORT,
            reason="",
        )
    except ValueError:
        pass
    else:
        notes.append("transition_without_reason_did_not_fail")

    return not notes, notes


def _missing_tokens(repo_root: Path, path: Path, tokens: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}:{token}" for token in tokens if not _contains(repo_root / path, token)]


def _build_payload(repo_root: Path) -> dict[str, Any]:
    notes: list[str] = []
    missing_files = [str(path) for path in REQUIRED_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_file:{path}" for path in missing_files)

    phase2_0_ok, phase2_0_payload, phase2_0_notes = _run_phase2_0_gate(repo_root)
    notes.extend(phase2_0_notes)

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
        ("claim-ledger.md", "check_scientist_best_in_class_phase2_1.py"),
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
    missing_mkdocs_tokens = _missing_tokens(
        repo_root,
        MKDOCS_CONFIG,
        MKDOCS_TOKENS,
        "missing_mkdocs_token",
    )
    notes.extend(missing_mkdocs_tokens)

    missing_integration_tokens: list[str] = []
    for path, tokens in INTEGRATION_TOKENS.items():
        text = _read_text(repo_root / path) if (repo_root / path).is_file() else ""
        missing_integration_tokens.extend(
            f"{path}:{token}" for token in tokens if token not in text
        )
    notes.extend(
        f"missing_phase2_1_integration_token:{token}" for token in missing_integration_tokens
    )

    category_results = {
        "deliverables_exist": not missing_files,
        "phase2_0_gate_green": phase2_0_ok,
        "lifecycle_contracts_validate": import_ok,
        "reference_doc_complete": not missing_reference_tokens,
        "active_plan_updated": not missing_plan_tokens,
        "readiness_doc_updated": not missing_readiness_tokens,
        "inventory_doc_updated": not missing_inventory_tokens,
        "scientist_index_updated": not missing_index_tokens,
        "mkdocs_nav_updated": not missing_mkdocs_tokens,
        "packet_and_bundle_projection_present": not missing_integration_tokens,
    }
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "phase2_0_gate_report": phase2_0_payload,
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
            "Scientist best-in-class Phase 2.1 is accepted"
            if status == "ok"
            else "Scientist best-in-class Phase 2.1 is incomplete"
        ),
        exit_code=0 if status == "ok" else 1,
        messages=tuple(
            ToolMessage(
                level="error" if status == "failed" else "info",
                message=str(note),
                rule_id="SCIENTIST_BEST_IN_CLASS_PHASE2_1",
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
