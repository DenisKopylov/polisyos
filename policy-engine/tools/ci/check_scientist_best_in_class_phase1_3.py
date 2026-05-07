#!/usr/bin/env python3
"""Validate the Scientist best-in-class Phase 1.3 deep research evidence stack."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase1_3"
TOOL_NAME = "ci.check-scientist-best-in-class-phase1-3"

REFERENCE_DOC = Path("docs/reference/scientist/deep-research-evidence.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
SCHOLAR_MODELS = Path("src/polisyos/scholar/search/models.py")
EVIDENCE_PACKAGE = Path("src/polisyos/scientist/evidence")
REQUIRED_PACKAGE_FILES: tuple[Path, ...] = (
    EVIDENCE_PACKAGE / "__init__.py",
    EVIDENCE_PACKAGE / "source_quality.py",
    EVIDENCE_PACKAGE / "snippet_ledger.py",
    EVIDENCE_PACKAGE / "claim_support.py",
    EVIDENCE_PACKAGE / "safe_fetch.py",
    EVIDENCE_PACKAGE / "cache.py",
    EVIDENCE_PACKAGE / "verifier.py",
    Path("src/polisyos/scientist/agent/tools/scholar_search_tools.py"),
    Path("src/polisyos/scientist/agent/tools/knowledge_tools_adapter.py"),
    Path("src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py"),
)
REQUIRED_TEST_FILES: tuple[Path, ...] = (
    Path("tests/unit/scientist/evidence/test_models.py"),
    Path("tests/unit/scientist/evidence/test_safe_fetch.py"),
    Path("tests/unit/scientist/evidence/test_source_quality.py"),
    Path("tests/unit/scientist/evidence/test_snippet_ledger.py"),
    Path("tests/unit/scientist/evidence/test_claim_support.py"),
    Path("tests/unit/scientist/evidence/test_cache.py"),
    Path("tests/unit/scientist/evidence/test_verifier.py"),
    Path("tests/unit/scientist/evidence/test_scholar_search_tools.py"),
    Path("tests/unit/scientist/evidence/test_research_dag_projection.py"),
    Path("tests/unit/scientist/evidence/test_decision_packet_web_evidence.py"),
    Path("tests/repo_quality/tools/test_scientist_best_in_class_phase1_3.py"),
)
REQUIRED_NEGATIVE_TEST_TOKENS: dict[Path, tuple[str, ...]] = {
    Path("tests/unit/scientist/evidence/test_safe_fetch.py"): (
        "169.254.169.254",
        "localhost",
        "blocked_domain",
        "blocked_content_type",
        "prompt_injection_suspected",
    ),
    Path("tests/unit/scientist/evidence/test_models.py"): ("missing snippet_id",),
    Path("tests/unit/scientist/evidence/test_scholar_search_tools.py"): (
        "blocked_private_network",
        "invalid_arguments",
    ),
}
REFERENCE_TOKENS: tuple[str, ...] = (
    "WebEvidenceBundle",
    "FetchSafetyEvent",
    "SourceQualitySignal",
    "untrusted evidence data",
    "SSRF",
    "claim-support links with missing snippet ids fail validation",
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    sys.path.insert(0, str(repo_root / "src"))
    notes: list[str] = []
    try:
        from polisyos.scholar.search.models import (
            ClaimSupportLink,
            QueryGraph,
            ResearchBrief,
            SearchConstraints,
            SourceMetadata,
            WebEvidenceBundle,
        )
        from polisyos.scientist.evidence.safe_fetch import evaluate_fetch_request
        from polisyos.scientist.evidence.source_quality import score_source_quality
        from pydantic import ValidationError
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return False, [f"phase1_3_import_failed:{exc.__class__.__name__}:{exc}"]

    try:
        brief = ResearchBrief(question="gate")
        WebEvidenceBundle(
            bundle_id="gate",
            brief=brief,
            query_graph=QueryGraph(brief=brief),
            sources=[
                SourceMetadata(
                    source_id="src.1",
                    url="https://agency.gov/report",
                    domain="agency.gov",
                )
            ],
            claim_supports=[
                ClaimSupportLink(
                    claim_id="claim.1",
                    claim_text="gate",
                    snippet_ids=["missing"],
                    source_ids=["src.1"],
                    support_score=0.5,
                    metadata={"support_status": "supported"},
                )
            ],
        )
        notes.append("missing_snippet_fixture_did_not_fail")
    except ValidationError:
        pass
    events = evaluate_fetch_request(
        "http://169.254.169.254/latest/meta-data",
        constraints=SearchConstraints(),
    )
    if not events or events[0].event_type != "blocked_private_network":
        notes.append("malicious_url_fixture_did_not_block")
    signal = score_source_quality(
        SourceMetadata(
            source_id="src.1",
            url="https://agency.gov/report",
            domain="agency.gov",
            source_type="government",
        )
    )
    if signal.authority_score <= 0:
        notes.append("source_quality_signal_invalid")
    return not notes, notes


def _build_payload(repo_root: Path) -> dict[str, object]:
    notes: list[str] = []
    missing_package_files = [
        str(path) for path in REQUIRED_PACKAGE_FILES if not (repo_root / path).is_file()
    ]
    missing_tests = [str(path) for path in REQUIRED_TEST_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_package_file:{path}" for path in missing_package_files)
    notes.extend(f"missing_test_file:{path}" for path in missing_tests)

    scholar_model_tokens = (
        "class FetchSafetyEvent",
        "class SourceQualitySignal",
        "fetch_safety_events",
        "source_quality_signals",
    )
    missing_scholar_tokens = [
        token for token in scholar_model_tokens if not _contains(repo_root / SCHOLAR_MODELS, token)
    ]
    notes.extend(f"missing_scholar_model_token:{token}" for token in missing_scholar_tokens)

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

    import_ok, import_notes = _import_and_validate(repo_root)
    notes.extend(import_notes)

    reference_exists = (repo_root / REFERENCE_DOC).is_file()
    if not reference_exists:
        notes.append(f"missing_reference_doc:{REFERENCE_DOC}")
    missing_reference_tokens = [
        token for token in REFERENCE_TOKENS if not _contains(repo_root / REFERENCE_DOC, token)
    ]
    notes.extend(f"missing_reference_token:{token}" for token in missing_reference_tokens)

    integration_tokens = {
        Path("src/polisyos/scientist/agent/tools/scholar_search_tools.py"): (
            "evaluate_fetch_request",
            "detect_prompt_injection",
            "MAX_FETCH_BYTES",
        ),
        Path("src/polisyos/scientist/agent/knowledge_tools.py"): (
            "untrusted evidence data",
            "fetch_safety_events",
            "source_quality_signals",
        ),
        Path("src/polisyos/scientist/methods/research_dag/projections.py"): (
            "project_web_evidence_bundle_to_research_dag",
            "scholar.web_evidence_bundle",
        ),
        Path("src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py"): (
            "ARTIFACT_WEB_EVIDENCE_BUNDLE_REF",
            "_build_web_evidence_section",
            "untrusted_evidence_text",
        ),
    }
    missing_integration_tokens: list[str] = []
    for path, tokens in integration_tokens.items():
        text = _read_text(repo_root / path) if (repo_root / path).is_file() else ""
        missing_integration_tokens.extend(
            f"{path}:{token}" for token in tokens if token not in text
        )
    notes.extend(
        f"missing_phase1_3_integration_token:{token}" for token in missing_integration_tokens
    )

    active_plan_tokens = ("1.3", "Deep research evidence", "closed")
    active_plan_missing = [
        token for token in active_plan_tokens if not _contains(repo_root / ACTIVE_PLAN_DOC, token)
    ]
    notes.extend(f"missing_active_plan_token:{token}" for token in active_plan_missing)

    category_results = {
        "canonical_scholar_contract_extended": not missing_scholar_tokens,
        "package_files_exist": not missing_package_files,
        "models_import_and_validate": import_ok,
        "reference_doc_complete": reference_exists and not missing_reference_tokens,
        "tests_present": not missing_tests,
        "negative_tests_cover_required_cases": not missing_negative_test_tokens,
        "integration_targets_use_phase1_3_helpers": not missing_integration_tokens,
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
        "notes": notes,
    }


def _phase1_3_result(payload: dict[str, object]) -> ToolResult:
    notes = payload.get("notes")
    note_list = list(notes) if isinstance(notes, list) else []
    status = "ok" if payload.get("passes_all") else "failed"
    summary = (
        "Scientist best-in-class Phase 1.3 deep research evidence is complete"
        if status == "ok"
        else "Scientist best-in-class Phase 1.3 deep research evidence is incomplete"
    )
    messages = tuple(
        ToolMessage(
            level="error" if status == "failed" else "info",
            message=str(note),
            rule_id="SCIENTIST_BEST_IN_CLASS_PHASE1_3",
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
    result = _phase1_3_result(payload)
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
