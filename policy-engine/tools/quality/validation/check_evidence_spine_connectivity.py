#!/usr/bin/env python3
"""Check scenario evidence contract propagation inside a canary evidence bundle."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.evidence_spine import (
    build_scenario_contract_propagation_graph,
)

SCHEMA_VERSION = "policyos.evidence_spine_connectivity_check.v1"
GRAPH_FILENAME = "scenario_contract_propagation_graph.json"

QUALITY_REPORT_FILES = {
    "golden_scenario_contract": "golden_scenario_contract.json",
    "production_data_quality": "production_data_quality.json",
    "normative_evidence": "normative_evidence.json",
    "fabric_retrieval_trace": "fabric_retrieval_trace.json",
    "foundry_method_report": "foundry_method_report.json",
    "policy_grounding_matrix": "policy_grounding_matrix.json",
    "semantic_binding_ledger": "semantic_binding_ledger.json",
    "policy_design_case": "policy_design_case.json",
    "scenario_contract_propagation_graph": GRAPH_FILENAME,
}


def inspect_bundle(bundle_dir: str | Path) -> dict[str, Any]:
    """Inspect one canary bundle and return a structured connectivity report."""

    bundle_path = Path(bundle_dir)
    request_payload = _load_optional_json(bundle_path / "request.sanitized.json")
    bundle_payload = _load_optional_json(bundle_path / "bundle.json")
    quality_evidence = _load_quality_evidence(bundle_path)
    graph = build_scenario_contract_propagation_graph(
        request_payload=request_payload,
        bundle_payload=bundle_payload,
        quality_evidence_payload=quality_evidence,
        bundle_ref=str(bundle_path),
        authority_profile=_canary_kind(bundle_payload),
        code_revision=_code_revision(bundle_payload),
    )
    findings = [
        dict(item)
        for item in graph.get("findings", [])
        if isinstance(item, Mapping) and item.get("status") == "fail"
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if findings else "pass",
        "bundle_dir": str(bundle_path),
        "summary": {
            "finding_count": len(findings),
            "node_count": graph.get("summary", {}).get("node_count", 0)
            if isinstance(graph.get("summary"), Mapping)
            else 0,
            "graph_status": graph.get("status"),
        },
        "findings": findings,
        "graph": graph,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    bundle_dir = args.bundle_dir
    if not bundle_dir.is_absolute():
        bundle_dir = repo_root / bundle_dir
    if not bundle_dir.exists():
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "fail",
            "bundle_dir": str(bundle_dir),
            "summary": {"finding_count": 1, "node_count": 0, "graph_status": "fail"},
            "findings": [
                {
                    "status": "fail",
                    "severity": "error",
                    "code": "evidence_spine_bundle_missing",
                    "message": f"Bundle directory does not exist: {bundle_dir}",
                    "artifact_ref": str(bundle_dir),
                    "root_cause_class": "evidence_spine_connectivity",
                    "next_action": "Provide a canary evidence bundle directory to inspect.",
                }
            ],
            "graph": None,
        }
    else:
        report = inspect_bundle(bundle_dir)

    if args.json_output is not None:
        output_path = args.json_output
        if not output_path.is_absolute():
            output_path = repo_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    if args.require_passing and report["status"] != "pass":
        return 2
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument("--require-passing", action="store_true")
    return parser.parse_args(argv)


def _load_quality_evidence(bundle_dir: Path) -> dict[str, Any]:
    quality_dir = bundle_dir / "quality_evidence"
    evidence: dict[str, Any] = {}
    for key, filename in QUALITY_REPORT_FILES.items():
        payload = _load_optional_json(quality_dir / filename)
        if payload:
            evidence[key] = payload
    return evidence


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "schema_version": "policyos.invalid_json.v1",
            "status": "fail",
            "issues": [
                {
                    "code": "invalid_json",
                    "message": f"{path}: {exc}",
                }
            ],
        }
    return payload if isinstance(payload, dict) else {}


def _canary_kind(bundle_payload: Mapping[str, Any]) -> str | None:
    value = bundle_payload.get("canary_kind")
    return str(value).strip() if value is not None and str(value).strip() else None


def _code_revision(bundle_payload: Mapping[str, Any]) -> str | None:
    value = bundle_payload.get("git_sha")
    if value is None:
        command = bundle_payload.get("command")
        if isinstance(command, Mapping):
            value = command.get("git_sha")
    return str(value).strip() if value is not None and str(value).strip() else None


if __name__ == "__main__":
    raise SystemExit(main())
