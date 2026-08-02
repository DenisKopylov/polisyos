#!/usr/bin/env python3
"""Validate the Layer 3 GY DesignProblem contract artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.lib.timing import run_timed_entrypoint

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_design_problem_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.design_problem_contract.v1"


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def build_live_payload() -> dict[str, Any]:
    """Recompute the DesignProblem contract payload from the live Pydantic model."""

    from polisyos.runtime.quality.design_problem import (
        DESIGN_PROBLEM_SCHEMA_VERSION,
        DesignProblem,
    )

    schema = DesignProblem.model_json_schema()
    return {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.design_problem",
        "design_problem_schema_version": DESIGN_PROBLEM_SCHEMA_VERSION,
        "owner": "polisyos.runtime.quality.design_problem.DesignProblem",
        "source_module": "src/polisyos/runtime/quality/design_problem.py",
        "projection_surfaces": [
            "runtime.PolicyIntentEnvelope",
            "scientist.agent.ProblemFrame",
            "ir.governance.ProblemFrame",
            "ir.model_layer.ModelSpec",
            "scientist.policy_verified.PolicyRequestFrame",
            "runtime.quality.workspace.WorkspaceLoop.run_intent",
        ],
        "strangle_obligations": [
            "plain_policy_nl_not_verified_default",
            "workspace_run_intent_rejects_raw_dict",
        ],
        "json_schema": schema,
    }


def validate(repo_root: Path) -> dict[str, Any]:
    """Validate the committed schema artifact against live code."""

    path = repo_root / OUTPUT_PATH
    issues: list[dict[str, Any]] = []
    live = build_live_payload()
    if not path.is_file():
        issues.append({"code": "design_problem_contract_missing", "path": OUTPUT_PATH})
        committed: dict[str, Any] | None = None
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            committed = None
            issues.append(
                {
                    "code": "design_problem_contract_invalid_json",
                    "path": OUTPUT_PATH,
                    "error": str(exc),
                }
            )
    if committed is not None and committed != live:
        issues.append({"code": "design_problem_contract_drift", "path": OUTPUT_PATH})
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
    }


def write(repo_root: Path) -> None:
    """Write the live DesignProblem contract artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_live_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    """Run the DesignProblem contract validator."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    inserted = [str(repo_root), str(repo_root / "src")]
    for item in reversed(inserted):
        if item not in sys.path:
            sys.path.insert(0, item)
    if args.write:
        write(repo_root)
    report = validate(repo_root)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "pass":
        for issue in report["issues"]:
            print(f"{issue.get('code')}: {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
