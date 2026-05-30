#!/usr/bin/env python3
"""Validate W11.C expert adjudication labels for the outcome corpus."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.corpus import (  # noqa: E402
    EXPERT_ADJUDICATION_SCHEMA_VERSION,
    build_expert_adjudication_useful_design_gate,
    evaluate_expert_adjudication_manifest,
)

DEFAULT_ADJUDICATION_ROOT = Path(
    "docs/research/universal-policy-design/outcome-corpus/adjudications"
)
TOOL_NAME = "quality.validation.check-expert-adjudication-labels"


def load_expert_adjudication_manifests(
    repo_root: Path = REPO_ROOT,
    *,
    adjudication_root: Path = DEFAULT_ADJUDICATION_ROOT,
) -> list[dict[str, Any]]:
    """Load committed W11.C expert adjudication JSON manifests."""

    root = _resolve_repo_path(repo_root, adjudication_root)
    manifests: list[dict[str, Any]] = []
    if not root.exists():
        return manifests
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            manifests.append({"__path__": path.relative_to(repo_root).as_posix(), **payload})
        else:
            manifests.append({"__path__": path.relative_to(repo_root).as_posix()})
    return manifests


def validate_expert_adjudication_labels(
    repo_root: Path = REPO_ROOT,
    *,
    adjudication_root: Path = DEFAULT_ADJUDICATION_ROOT,
) -> dict[str, Any]:
    """Validate W11.C manifests and aggregate label/topology coverage."""

    manifests = load_expert_adjudication_manifests(
        repo_root,
        adjudication_root=adjudication_root,
    )
    issues: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    topology_modes: Counter[str] = Counter()

    if not manifests:
        issues.append(
            _issue(
                "expert_adjudication_manifest_missing",
                adjudication_root.as_posix(),
                "W11.C requires at least one repo-owned expert adjudication manifest.",
            )
        )

    for manifest in manifests:
        manifest_path = str(manifest.get("__path__") or "<unknown>")
        payload = {key: value for key, value in manifest.items() if key != "__path__"}
        result = evaluate_expert_adjudication_manifest(payload)
        evaluations.append({"path": manifest_path, **result})
        if payload.get("schema_version") != EXPERT_ADJUDICATION_SCHEMA_VERSION:
            issues.append(
                _issue(
                    "expert_adjudication_schema_version_invalid",
                    manifest_path,
                    f"schema_version must be {EXPERT_ADJUDICATION_SCHEMA_VERSION}",
                )
            )
        if result["status"] != "pass":
            for result_issue in _sequence_of_mappings(result.get("issues")):
                issues.append(
                    _issue(
                        str(result_issue.get("code") or "expert_adjudication_invalid"),
                        manifest_path,
                        str(result_issue.get("message") or "Manifest failed validation."),
                    )
                )
            continue
        label_counts.update(str(label) for label in result["labels"])
        if result.get("topology_mode"):
            topology_modes[str(result["topology_mode"])] += 1

    missing_gate = build_expert_adjudication_useful_design_gate(
        case_id="w11c-missing-adjudication-negative",
        structural_complete=True,
        adjudication_result=None,
    )
    if missing_gate["counts_toward_useful_design"] is not False:
        issues.append(
            _issue(
                "expert_adjudication_missing_gate_not_blocking",
                "useful_design_gate",
                "A structurally complete case without W11.C labels must not count.",
            )
        )

    return {
        "schema_version": (
            "policyos.universal_policy_design.outcome_corpus."
            "expert_adjudication.validation.v1"
        ),
        "tool": TOOL_NAME,
        "status": "fail" if issues else "pass",
        "manifest_count": len(manifests),
        "label_counts": dict(sorted(label_counts.items())),
        "topology_modes": dict(sorted(topology_modes.items())),
        "evaluations": evaluations,
        "useful_design_gate": {
            "missing_adjudication_blocks": missing_gate["blocker_code"]
            == "expert_adjudication_missing"
            and missing_gate["counts_toward_useful_design"] is False,
            "negative_gate": missing_gate,
        },
        "issues": issues,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the W11.C expert adjudication label validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--adjudication-root",
        type=Path,
        default=DEFAULT_ADJUDICATION_ROOT,
    )
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    result = validate_expert_adjudication_labels(
        repo_root,
        adjudication_root=args.adjudication_root,
    )
    if args.json_output:
        atomic_write_json(args.json_output, result)
    if result["status"] != "pass":
        sys.stderr.write(json.dumps(result, indent=2, ensure_ascii=False))
        sys.stderr.write("\n")
        return 1
    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _sequence_of_mappings(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _issue(code: str, field: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "field": field,
        "message": message,
    }


if __name__ == "__main__":
    raise SystemExit(main())
