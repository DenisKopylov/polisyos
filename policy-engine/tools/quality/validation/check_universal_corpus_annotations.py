#!/usr/bin/env python3
"""Validate W11.B universal outcome corpus claim/evidence annotations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.corpus import (
    load_policy_case_annotation,
    policy_case_annotation_audit_surface,
)

SCHEMA_VERSION = "policyos.universal_outcome_corpus.annotation_check.v1"
DEFAULT_CORPUS_DIR = Path("docs/research/universal-policy-design/outcome-corpus")
CAPABILITY_ID = "w11b_claim_evidence_decomposition_annotations"
PATTERN_REFS = ("P01", "P02", "P03", "P05", "P10", "P13", "P14", "P15")

if TYPE_CHECKING:
    from collections.abc import Sequence


def build_report(
    *,
    repo_root: Path,
    corpus_dir: Path | None = None,
) -> dict[str, Any]:
    """Build a W11.B annotation validation report."""

    root = repo_root.resolve()
    directory = _resolve_corpus_dir(repo_root=root, corpus_dir=corpus_dir)
    findings: list[dict[str, Any]] = []
    case_surfaces: list[dict[str, Any]] = []

    if not directory.exists():
        findings.append(
            _finding(
                code="outcome_corpus_missing",
                message=f"Universal outcome corpus directory does not exist: {directory}",
                artifact_ref=_repo_ref(root, directory),
            )
        )
    else:
        case_paths = [
            path
            for path in sorted(directory.glob("*.md"))
            if path.name.casefold() != "readme.md"
        ]
        if not case_paths:
            findings.append(
                _finding(
                    code="outcome_corpus_empty",
                    message=f"Universal outcome corpus has no Markdown case files: {directory}",
                    artifact_ref=_repo_ref(root, directory),
                )
            )
        for path in case_paths:
            try:
                annotation = load_policy_case_annotation(path)
            except (ValidationError, ValueError) as exc:
                findings.append(
                    _finding(
                        code="annotation_invalid",
                        message=str(exc),
                        artifact_ref=_repo_ref(root, path),
                    )
                )
                continue
            case_surfaces.append(policy_case_annotation_audit_surface(annotation))

    summary = {
        "case_count": len(case_surfaces),
        "claim_count": sum(surface["summary"]["claim_count"] for surface in case_surfaces),
        "obligation_count": sum(
            surface["summary"]["obligation_count"] for surface in case_surfaces
        ),
        "known_outcome_or_failure_count": sum(
            surface["summary"]["known_outcome_or_failure_count"]
            for surface in case_surfaces
        ),
        "finding_count": len(findings),
    }
    status = "pass" if not findings and summary["case_count"] > 0 else "fail"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "corpus_dir": _repo_ref(root, directory),
        "summary": summary,
        "cases": case_surfaces,
        "findings": findings,
        "capability_trace": {
            "capability_id": CAPABILITY_ID,
            "capability_reality_label": (
                "implemented" if status == "pass" else "artifact_missing"
            ),
            "typed_contract_ref": "repo://src/polisyos/corpus/annotations.py",
            "producer_ref": (
                "repo://docs/research/universal-policy-design/outcome-corpus"
            ),
            "artifact_ref": (
                "repo://docs/research/universal-policy-design/outcome-corpus"
            ),
            "bridge_ref": (
                "repo://tools/quality/validation/check_universal_corpus_annotations.py"
            ),
            "consumer_ref": (
                "repo://tools/quality/validation/check_universal_corpus_annotations.py"
            ),
            "verification_ref": (
                "repo://tests/repo_quality/tools/test_universal_corpus_annotations.py"
            ),
            "surface_ref": (
                "repo://docs/research/universal-policy-design/outcome-corpus/README.md"
            ),
            "semantic_test_ref": (
                "repo://tests/unit/corpus/test_annotations.py"
                "#test_claim_refs_must_be_grounded_in_case_reference_index"
            ),
            "missing_capability_labels": [] if status == "pass" else ["artifact_missing"],
        },
        "pattern_pass": {
            "relevant_patterns": list(PATTERN_REFS),
            "target_correct_pattern": (
                "W11.B annotations are persisted reviewer artifacts consumed by "
                "truthfulness checks, with authority-bearing uses explicitly forbidden."
            ),
            "existing_anti_patterns_found": (
                []
                if status == "pass"
                else ["artifact_missing: no valid claim/evidence annotation artifact"]
            ),
            "acceptance_signal": (
                "every loaded case has claim records, obligation annotations, known "
                "outcome/failure records, source grounding, and an audit authority boundary"
            ),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for W11.B annotation validation."""

    args = _parse_args(argv)
    report = build_report(repo_root=args.repo_root, corpus_dir=args.corpus_dir)
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_output is not None:
        output_path = args.json_output
        if not output_path.is_absolute():
            output_path = args.repo_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    if args.check and report["status"] != "pass":
        return 2
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--corpus-dir", type=Path, default=None)
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def _resolve_corpus_dir(*, repo_root: Path, corpus_dir: Path | None) -> Path:
    if corpus_dir is None:
        return repo_root / DEFAULT_CORPUS_DIR
    if corpus_dir.is_absolute():
        return corpus_dir
    return repo_root / corpus_dir


def _finding(*, code: str, message: str, artifact_ref: str) -> dict[str, str]:
    return {
        "code": code,
        "message": message,
        "artifact_ref": artifact_ref,
    }


def _repo_ref(repo_root: Path, path: Path) -> str:
    try:
        return f"repo://{path.resolve().relative_to(repo_root)}"
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
