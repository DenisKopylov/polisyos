#!/usr/bin/env python3
"""Validate the Scientist Phase 1.5 benchmark authority surface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_benchmark_authority_phase1_5"
TOOL_NAME = "ci.check-scientist-benchmark-authority"

REFERENCE_DOC = Path("docs/reference/scientist/benchmark-authority.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
REQUIRED_PACKAGE_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/evals/__init__.py"),
    Path("src/polisyos/scientist/evals/authority.py"),
    Path("src/polisyos/scientist/evals/datasets.py"),
    Path("src/polisyos/scientist/evals/graders.py"),
    Path("src/polisyos/scientist/evals/leakage.py"),
    Path("src/polisyos/scientist/evals/frozen_web.py"),
    Path("src/polisyos/scientist/evals/policy_cases.py"),
    Path("src/polisyos/scientist/evals/challenge_packs.py"),
    Path("src/polisyos/scientist/evals/reports.py"),
    Path("src/polisyos/scientist/agent/promotion.py"),
    Path("src/polisyos/scientist/orchestration/engine/frontier_runtime.py"),
)
REQUIRED_TEST_FILES: tuple[Path, ...] = (
    Path("tests/unit/scientist/evals/test_authority.py"),
    Path("tests/unit/scientist/evals/test_datasets.py"),
    Path("tests/unit/scientist/evals/test_leakage.py"),
    Path("tests/unit/scientist/evals/test_graders.py"),
    Path("tests/unit/scientist/evals/test_frozen_web.py"),
    Path("tests/unit/scientist/evals/test_policy_cases.py"),
    Path("tests/unit/scientist/evals/test_challenge_packs.py"),
    Path("tests/unit/scientist/evals/test_authority_integration.py"),
    Path("tests/unit/scientist/search/test_benchmark_registry.py"),
    Path("tests/unit/scientist/search/test_phase_d4_runtime_integration.py"),
    Path("tests/unit/scientist/search/test_frontier_runtime.py"),
    Path("tests/repo_quality/tools/test_scientist_benchmark_authority.py"),
)
REQUIRED_SPLIT_DOC_TOKENS: tuple[str, ...] = (
    "`public`",
    "`private`",
    "`hidden_holdout`",
    "`rotating_challenge`",
    "`sentinel`",
    "`adversarial`",
)
REFERENCE_TOKENS: tuple[str, ...] = (
    "BenchmarkAuthority",
    "PromotionEvidenceRequest",
    "BenchmarkAuthorityVerdict",
    "BenchmarkRegistry",
    "stale",
    "hidden holdout",
    "public_export",
)
NEGATIVE_TEST_TOKENS: dict[Path, tuple[str, ...]] = {
    Path("tests/unit/scientist/evals/test_authority.py"): (
        "hidden_holdout_evaluation_ref",
        "rotating_challenge_evaluation_refs",
        "revision_status",
        "benchmark_pack_ref",
        "registered_benchmark_pack_ref",
    ),
    Path("tests/unit/scientist/evals/test_leakage.py"): (
        "public_verdict_export_redacts_hidden_holdout_refs",
        "detect_benchmark_contamination",
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
        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.evals.authority import (
            BenchmarkAuthority,
            PromotionEvidenceRequest,
        )
        from polisyos.scientist.evals.datasets import BENCHMARK_AUTHORITY_SPLIT_NAMES
        from polisyos.scientist.evals.leakage import (
            detect_benchmark_contamination,
            public_payload_contains_hidden_refs,
        )
        from polisyos.scientist.search.benchmark_registry import BenchmarkRegistry
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return False, [f"benchmark_authority_import_failed:{exc.__class__.__name__}:{exc}"]

    required_splits = {
        "public",
        "private",
        "hidden_holdout",
        "rotating_challenge",
        "sentinel",
        "adversarial",
    }
    if not required_splits.issubset(set(BENCHMARK_AUTHORITY_SPLIT_NAMES)):
        notes.append("split_taxonomy_missing_required_names")

    def _ref(seed: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=ArtifactID.model_validate("sha256:" + seed * 64),
            kind="scientist.benchmark_evaluation",
            media_type="application/json",
        )

    with TemporaryDirectory() as tmp:
        registry = BenchmarkRegistry(Path(tmp) / "benchmarks")
        registry.record("selection", _ref("a"), family="policy_design", loop_id="loop-a")
        blocked = BenchmarkAuthority(registry).verdict(
            PromotionEvidenceRequest(
                family="policy_design",
                claim_mode="estimation",
                loop_id="loop-a",
            )
        )
        if blocked.default_enable_allowed:
            notes.append("missing_evidence_fixture_did_not_block")
        if "hidden_holdout_evaluation_ref" not in blocked.missing:
            notes.append("missing_hidden_holdout_not_reported")
        unregistered = BenchmarkAuthority(registry).verdict(
            PromotionEvidenceRequest(
                family="policy_design",
                claim_mode="estimation",
                loop_id="loop-a",
                benchmark_pack_ref=_ref("d"),
            )
        )
        if "registered_benchmark_pack_ref" not in unregistered.missing:
            notes.append("unregistered_benchmark_pack_ref_did_not_block")
        registry.record(
            "hidden_holdout",
            _ref("b"),
            family="policy_design",
            loop_id="loop-a",
            metadata={
                "revision_status": "stale",
                "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            },
        )
        registry.record(
            "rotating_challenge",
            _ref("c"),
            family="policy_design",
            loop_id="loop-a",
        )
        stale = BenchmarkAuthority(registry).verdict(
            PromotionEvidenceRequest(
                family="policy_design",
                claim_mode="estimation",
                loop_id="loop-a",
            )
        )
        if stale.default_enable_allowed:
            notes.append("stale_evidence_fixture_did_not_block")
        if not stale.stale:
            notes.append("stale_fixture_missing_stale_reasons")
        hidden_ids = {str(stale.bundle.hidden_holdout_evaluation_ref.artifact_id)}
        public_payload = stale.public_export()
        if public_payload_contains_hidden_refs(public_payload, hidden_ref_ids=hidden_ids):
            notes.append("public_export_leaked_hidden_refs")
        if not detect_benchmark_contamination(
            {"suite": "hidden-suite-v1"},
            hidden_ref_ids=set(),
            hidden_suite_ids={"hidden-suite-v1"},
        ):
            notes.append("contamination_fixture_did_not_detect_suite_token")
    return not notes, notes


def _build_payload(repo_root: Path) -> dict[str, object]:
    notes: list[str] = []
    missing_package_files = [
        str(path) for path in REQUIRED_PACKAGE_FILES if not (repo_root / path).is_file()
    ]
    missing_tests = [str(path) for path in REQUIRED_TEST_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_package_file:{path}" for path in missing_package_files)
    notes.extend(f"missing_test_file:{path}" for path in missing_tests)

    import_ok, import_notes = _import_and_validate(repo_root)
    notes.extend(import_notes)

    reference_exists = (repo_root / REFERENCE_DOC).is_file()
    if not reference_exists:
        notes.append(f"missing_reference_doc:{REFERENCE_DOC}")
    missing_reference_tokens = [
        token for token in REFERENCE_TOKENS if not _contains(repo_root / REFERENCE_DOC, token)
    ]
    missing_split_tokens = [
        token
        for token in REQUIRED_SPLIT_DOC_TOKENS
        if not _contains(repo_root / REFERENCE_DOC, token)
    ]
    notes.extend(f"missing_reference_token:{token}" for token in missing_reference_tokens)
    notes.extend(f"missing_split_doc_token:{token}" for token in missing_split_tokens)

    missing_negative_test_tokens: list[str] = []
    for path, tokens in NEGATIVE_TEST_TOKENS.items():
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

    integration_tokens = {
        Path("src/polisyos/scientist/agent/promotion.py"): (
            "benchmark_authority_verdict",
            "require_benchmark_authority",
            "benchmark_authority_not_allowed",
        ),
        Path("src/polisyos/scientist/orchestration/engine/frontier_runtime.py"): (
            "require_benchmark_authority",
            "benchmark_authority_default_enable_allowed",
        ),
    }
    missing_integration_tokens: list[str] = []
    for path, tokens in integration_tokens.items():
        text = _read_text(repo_root / path) if (repo_root / path).is_file() else ""
        missing_integration_tokens.extend(
            f"{path}:{token}" for token in tokens if token not in text
        )
    notes.extend(
        f"missing_phase1_5_integration_token:{token}" for token in missing_integration_tokens
    )

    active_plan_tokens = ("1.5", "Benchmark authority", "closed")
    active_plan_missing = [
        token for token in active_plan_tokens if not _contains(repo_root / ACTIVE_PLAN_DOC, token)
    ]
    notes.extend(f"missing_active_plan_token:{token}" for token in active_plan_missing)

    category_results = {
        "package_files_exist": not missing_package_files,
        "tests_present": not missing_tests,
        "models_import_and_validate": import_ok,
        "reference_doc_complete": (
            reference_exists and not missing_reference_tokens and not missing_split_tokens
        ),
        "negative_tests_cover_required_cases": not missing_negative_test_tokens,
        "agent_and_frontier_shadow_integration_present": not missing_integration_tokens,
        "active_plan_updated": not active_plan_missing,
    }
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "required_package_files": [str(path) for path in REQUIRED_PACKAGE_FILES],
        "required_test_files": [str(path) for path in REQUIRED_TEST_FILES],
        "notes": notes,
    }


def _benchmark_authority_result(payload: dict[str, object]) -> ToolResult:
    notes = payload.get("notes")
    note_list = list(notes) if isinstance(notes, list) else []
    status = "ok" if payload.get("passes_all") else "failed"
    summary = (
        "Scientist benchmark authority Phase 1.5 is complete"
        if status == "ok"
        else "Scientist benchmark authority Phase 1.5 is incomplete"
    )
    messages = tuple(
        ToolMessage(
            level="error" if status == "failed" else "info",
            message=str(note),
            rule_id="SCIENTIST_BENCHMARK_AUTHORITY_PHASE1_5",
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
    result = _benchmark_authority_result(payload)
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
