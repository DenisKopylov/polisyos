#!/usr/bin/env python3
"""Run the W12.E bundle, replay, and inspection phase."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.lib.runner import render_command

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.argument_graph import (  # noqa: E402
    build_argument_graph,
    inspect_argument_graph,
)

SCHEMA_VERSION = "policyos.policy_design_case.w12e.bundle_replay_inspection.v1"
MANIFEST_SCHEMA_VERSION = (
    "policyos.policy_design_case.wave12e.bundle_replay_inspection_manifest.v1"
)
TOOL_NAME = "quality.validation.run-policy-design-case-bundle-replay-inspection"
GENERATED_AT = "2026-05-25T00:00:00Z"
PHASE_ID = "W12.E"
PHASE_NAME = "Bundle, Replay, And Inspection"
DEFAULT_W12D_REPORT = Path(
    "_build/.tmp/production-quality/w12d_universal_outcome_corpus_run.json"
)
DEFAULT_OUTPUT = Path(
    "_build/.tmp/production-quality/w12e_bundle_replay_inspection.json"
)
DEFAULT_MANIFEST_OUTPUT = Path(
    "architecture/policy_design_case/wave12e_bundle_replay_inspection_manifest.json"
)

REQUIRED_COMPONENT_IDS = (
    "spine",
    "handoff",
    "claim_registry",
    "pdc_graph",
    "argument_graph",
    "conflict_records",
    "effective_independence_graph",
    "pdc_projection",
    "closeout",
    "compatibility",
    "rule_refs",
    "tuned_config_refs",
    "source_provenance",
    "hypothesis_ledger_excerpts",
    "inspected_artifact_refs",
)
FORBIDDEN_PACKAGING_AUTHORITY = frozenset(
    {
        "producer_domain_truth",
        "claim_evidence_authority",
        "production_closeout_authority",
        "public_projection_authority",
    }
)


def build_w12e_bundle_replay_inspection_report(
    *,
    w12d_report: Mapping[str, Any],
    repo_root: str | Path = REPO_ROOT,
    w12d_report_ref: str,
    extra_components: Sequence[Mapping[str, Any]] = (),
    generated_at: str = GENERATED_AT,
) -> dict[str, Any]:
    """Build the W12.E bundle inspection report from a W12.D run.

    Args:
        w12d_report: The W12.D universal outcome corpus report.
        repo_root: Product repository root recorded in the report.
        w12d_report_ref: Reference to the input W12.D report.
        extra_components: Optional caller-provided bundle components, mainly
            for negative tests and extension hooks.
        generated_at: Deterministic or runtime report timestamp.

    Returns:
        A JSON-serializable W12.E phase report.
    """

    cases = _sequence_of_mappings(w12d_report.get("cases"))
    components = _dedupe_components(
        [
            *(
                _component_from_case(
                    case,
                    component_id=component_id,
                    repo_root=Path(repo_root).resolve(),
                )
                for component_id in REQUIRED_COMPONENT_IDS
                for case in (cases or ({},))
            ),
            *[dict(component) for component in extra_components],
        ]
    )
    replay = _compare_replay_evidence_graph(w12d_report, components)
    blockers = [
        *_component_blockers(components),
        *_packaging_authority_blockers(components),
        *_replay_blockers(replay),
    ]
    present_required = {
        component["component_id"]
        for component in components
        if component.get("component_id") in REQUIRED_COMPONENT_IDS
        and component.get("status") == "present"
    }
    status = "blocked" if blockers else "pass"

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "phase_id": PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": generated_at,
        "repo_root": str(Path(repo_root).resolve()),
        "input_refs": {"w12d_report_ref": w12d_report_ref},
        "status": status,
        "summary": {
            "case_count": len(cases),
            "required_component_count": len(REQUIRED_COMPONENT_IDS),
            "present_component_count": len(present_required),
            "blocked_component_count": sum(
                1 for component in components if component.get("status") == "blocked"
            ),
            "replay_mismatch_count": int(replay["mismatch_count"]),
            "packaging_laundering_issue_count": sum(
                1
                for blocker in blockers
                if blocker["code"] == "w12e_packaging_summary_authority_laundering"
            ),
        },
        "bundle": {
            "schema_version": "policyos.policy_design_case.w12e.bundle.v1",
            "components": components,
        },
        "replay_evidence_graph_comparison": replay,
        "typed_blockers": blockers,
        "authority_boundary": _phase_authority_boundary(),
        "metric_policy": {
            "packaging_summaries_are_authority": False,
            "typed_blockers_count_as_useful_design": False,
            "typed_blockers_are_closeout_honesty_failures": False,
        },
        "pattern_pass": {
            "relevant_patterns": ["P01", "P03", "P05", "P07", "P10", "P12", "P15"],
            "target_correct_pattern": (
                "W12.E packages live W12.D graph evidence, checks deterministic replay, "
                "and blocks any attempt to upgrade package summaries into producer, "
                "claim, closeout, or public projection authority."
            ),
            "missing_capability_labels": _missing_labels(blockers),
        },
    }


def build_w12e_manifest() -> dict[str, Any]:
    """Build the deterministic W12.E command and authority contract."""

    command = (
        "uv",
        "run",
        "python",
        "tools/quality/validation/run_policy_design_case_bundle_replay_inspection.py",
        "--repo-root",
        ".",
        "--w12d-report",
        DEFAULT_W12D_REPORT.as_posix(),
        "--output",
        DEFAULT_OUTPUT.as_posix(),
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "implemented",
        "phase_id": PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": GENERATED_AT,
        "owner": "team-runtime-quality",
        "implementation_plan_ref": (
            "repo://docs/plans/active/"
            "POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
            "#w12e-bundle-replay-and-inspection"
        ),
        "tool_ref": (
            "repo://tools/quality/validation/"
            "run_policy_design_case_bundle_replay_inspection.py"
        ),
        "required_bundle_components": list(REQUIRED_COMPONENT_IDS),
        "command_contract": {
            "command": render_command(command),
            "output_refs": [DEFAULT_OUTPUT.as_posix()],
            "required_checks": [
                "bundle_component_presence",
                "replay_evidence_graph",
                "packaging_authority_boundary",
            ],
            "owner": "team-runtime-quality",
            "next_action": (
                "Repair missing W8 bundle components, replay drift, or authority "
                "laundering blockers before W12.F/G can consume the phase."
            ),
        },
        "metric_policy": {
            "packaging_summaries_are_authority": False,
            "typed_blockers_count_as_useful_design": False,
            "typed_blockers_are_closeout_honesty_failures": False,
        },
        "authority_boundary": _phase_authority_boundary(),
        "pattern_pass": {
            "relevant_patterns": ["P01", "P03", "P05", "P07", "P10", "P12", "P15"],
            "target_correct_pattern": (
                "Bundle inspection is a consumer of runtime evidence and replay refs; "
                "it never becomes producer or public projection authority."
            ),
            "missing_capability_labels": [],
        },
        "validation": {
            "test_ref": (
                "repo://tests/repo_quality/tools/"
                "test_w12e_bundle_replay_inspection.py"
            ),
            "command_ref": render_command(command),
        },
    }


def run_w12e_bundle_replay_inspection(
    *,
    repo_root: str | Path = REPO_ROOT,
    w12d_report_path: str | Path = DEFAULT_W12D_REPORT,
) -> dict[str, Any]:
    """Load W12.D evidence and return the W12.E inspection report."""

    root = Path(repo_root).resolve()
    path = _resolve(root, Path(w12d_report_path))
    report = _load_json(path)
    return build_w12e_bundle_replay_inspection_report(
        w12d_report=report,
        repo_root=root,
        w12d_report_ref=f"repo://{_repo_relative(root, path)}",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    if args.write_manifest:
        atomic_write_json(_resolve(repo_root, args.output), build_w12e_manifest())
        return 0

    report = run_w12e_bundle_replay_inspection(
        repo_root=repo_root,
        w12d_report_path=args.w12d_report,
    )
    atomic_write_json(_resolve(repo_root, args.output), report)
    if report["status"] == "pass" or args.allow_typed_blockers:
        return 0
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--w12d-report", type=Path, default=DEFAULT_W12D_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--allow-typed-blockers", action="store_true")
    return parser


def _component_from_case(
    case: Mapping[str, Any],
    *,
    component_id: str,
    repo_root: Path,
) -> dict[str, Any]:
    universal = _mapping(case.get("universal_compilation"))
    producer = _mapping(case.get("producer_pipeline"))
    llm = _mapping(case.get("llm_universal_compilation"))
    runtime_graph = _mapping(case.get("runtime_pdc_graph"))
    evidence_graph = _mapping(case.get("evidence_bound_pdc_graph"))
    graph_ref = str(runtime_graph.get("graph_ref") or "")
    artifact_ref = str(evidence_graph.get("artifact_ref") or graph_ref or "missing")
    case_id = str(case.get("case_id") or "unknown-case")
    base = {
        "component_id": component_id,
        "case_id": case_id,
        "status": "present",
        "authority_boundary": _component_authority_boundary(),
    }
    component_refs = {
        "spine": universal.get("grammar_ref"),
        "handoff": producer.get("producer_pipeline_ref"),
        "claim_registry": universal.get("claim_decomposition_ref"),
        "pdc_graph": artifact_ref,
        "argument_graph": f"{artifact_ref}#argument-graph",
        "conflict_records": f"{artifact_ref}#conflict-records",
        "effective_independence_graph": f"{artifact_ref}#effective-independence",
        "pdc_projection": _mapping(case.get("projection")).get(
            "projection_ref", f"{artifact_ref}#projection"
        ),
        "closeout": _mapping(case.get("closeout")).get(
            "closeout_ref", f"{artifact_ref}#closeout"
        ),
        "compatibility": _mapping(case.get("compatibility")).get(
            "compatibility_ref", f"{artifact_ref}#compatibility"
        ),
        "rule_refs": universal.get("rule_version_refs")
        or [universal.get("obligation_graph_ref")],
        "tuned_config_refs": universal.get("tuned_config_refs") or ["tuned-config:runtime"],
        "source_provenance": producer.get("source_provenance_refs")
        or [producer.get("producer_pipeline_ref")],
        "hypothesis_ledger_excerpts": (
            universal.get("hypothesis_ledger_artifact_ref")
            or llm.get("hypothesis_ledger_artifact_ref")
        ),
        "inspected_artifact_refs": [
            ref for ref in (artifact_ref, graph_ref) if isinstance(ref, str) and ref
        ],
    }
    ref_value = component_refs.get(component_id)
    missing = not _has_ref(ref_value)
    blocked_reasons: list[dict[str, Any]] = []
    argument_graph_inspection = (
        _argument_graph_inspection_from_runtime_artifact(
            repo_root=repo_root,
            artifact_ref=str(artifact_ref),
        )
        if component_id == "argument_graph"
        else None
    )
    if missing:
        blocked_reasons.append(
            _blocker(
                code="w12e_required_bundle_component_missing",
                message=f"W12.E required bundle component is missing: {component_id}.",
                owner="team-runtime-quality",
                component_id=component_id,
                capability_label="artifact_missing",
            )
        )
    if (
        component_id == "argument_graph"
        and not _argument_graph_component_has_warrants(
            runtime_graph=runtime_graph,
            inspection=argument_graph_inspection,
        )
    ):
        blocked_reasons.append(
            _blocker(
                code="w12e_argument_graph_incomplete",
                message=(
                    "W12.E could not inspect a W8.B argument graph with machine-readable "
                    "warrants from the runtime PDC graph artifact."
                ),
                owner="team-runtime-quality",
                component_id=component_id,
                capability_label="bridge_missing",
            )
        )
    if blocked_reasons:
        base["status"] = "blocked"
        base["blockers"] = blocked_reasons
    base["artifact_ref"] = ref_value
    base["summary"] = {
        "runtime_graph_ref": graph_ref,
        "claim_count": int(runtime_graph.get("claim_count") or 0),
        "edge_count": int(runtime_graph.get("edge_count") or 0),
        "warrant_structure_count": int(runtime_graph.get("warrant_structure_count") or 0),
    }
    if argument_graph_inspection is not None:
        base["summary"].update(argument_graph_inspection)
    if component_id == "argument_graph":
        base["summary"].update(
            _argument_graph_component_statuses(
                runtime_graph=runtime_graph,
                inspection=argument_graph_inspection,
            )
        )
    return base


def _argument_graph_component_has_warrants(
    *,
    runtime_graph: Mapping[str, Any],
    inspection: Mapping[str, Any] | None,
) -> bool:
    if inspection is not None:
        machine_warrants = int(inspection.get("machine_inspectable_warrant_count") or 0)
        return machine_warrants > 0
    return int(runtime_graph.get("warrant_structure_count") or 0) > 0


def _argument_graph_component_statuses(
    *,
    runtime_graph: Mapping[str, Any],
    inspection: Mapping[str, Any] | None,
) -> dict[str, str]:
    if inspection is None:
        bridge_status = (
            "pass" if int(runtime_graph.get("warrant_structure_count") or 0) > 0 else "blocked"
        )
        return {
            "argument_graph_bridge_status": bridge_status,
            "argument_graph_readiness_status": "unknown",
        }
    machine_warrants = int(inspection.get("machine_inspectable_warrant_count") or 0)
    issue_codes = set(_sequence(inspection.get("argument_graph_issue_codes")))
    if inspection.get("argument_graph_inspection_status") == "pass":
        readiness_status = "pass"
    elif issue_codes <= {"argument_graph_readiness_not_passing"}:
        readiness_status = "blocked"
    else:
        readiness_status = "blocked"
    return {
        "argument_graph_bridge_status": "pass" if machine_warrants > 0 else "blocked",
        "argument_graph_readiness_status": readiness_status,
    }


def _argument_graph_inspection_from_runtime_artifact(
    *,
    repo_root: Path,
    artifact_ref: str,
) -> dict[str, Any] | None:
    graph_path = _resolve_artifact_ref(repo_root, artifact_ref)
    if graph_path is None or not graph_path.exists():
        return None
    payload = _load_json(graph_path)
    argument_graph = build_argument_graph(payload)
    inspection = inspect_argument_graph(argument_graph)
    summary = _mapping(inspection.get("summary"))
    issue_codes = sorted(
        {
            str(issue.get("code"))
            for issue in _sequence_of_mappings(argument_graph.get("issues"))
            if issue.get("code")
        }
    )
    return {
        "argument_graph_status": argument_graph.get("status"),
        "argument_graph_inspection_status": inspection.get("status"),
        "argument_graph_claim_count": int(
            _mapping(argument_graph.get("summary")).get("claim_count") or 0
        ),
        "argument_graph_warrant_count": int(
            _mapping(argument_graph.get("summary")).get("warrant_count") or 0
        ),
        "machine_inspectable_warrant_count": int(
            summary.get("machine_inspectable_warrant_count") or 0
        ),
        "complete_claim_path_count": int(summary.get("complete_claim_path_count") or 0),
        "argument_graph_issue_codes": issue_codes,
    }


def _case_expected_negative_control(case: Mapping[str, Any]) -> bool:
    delta = _mapping(case.get("expert_adjudication_delta"))
    return (
        str(case.get("outcome") or "") == "typed_blocker"
        and str(delta.get("expected_outcome") or "") == "typed_blocker"
    )


def _resolve_artifact_ref(repo_root: Path, ref: str) -> Path | None:
    if not ref or ref == "missing":
        return None
    if "#" in ref:
        ref = ref.split("#", 1)[0]
    if ref.startswith("repo://"):
        value = ref.removeprefix("repo://")
        candidate = Path(value)
        return candidate if candidate.is_absolute() else repo_root / candidate
    candidate = Path(ref)
    return candidate if candidate.is_absolute() else repo_root / candidate


def _compare_replay_evidence_graph(
    w12d_report: Mapping[str, Any],
    components: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    cases = _sequence_of_mappings(w12d_report.get("cases"))
    live_graphs = [
        _mapping(case.get("runtime_pdc_graph"))
        for case in cases
        if _mapping(case.get("runtime_pdc_graph")).get("graph_ref")
    ]
    replay_graphs = [
        component
        for component in components
        if component.get("component_id") == "pdc_graph"
        and component.get("status") == "present"
    ]
    mismatches: list[dict[str, Any]] = []
    if len(live_graphs) != len(replay_graphs):
        mismatches.append(
            {
                "code": "w12e_replay_graph_count_mismatch",
                "live_graph_count": len(live_graphs),
                "replay_graph_count": len(replay_graphs),
            }
        )
    for case, component in zip(live_graphs, replay_graphs, strict=False):
        if str(case.get("graph_ref")) not in json.dumps(component, sort_keys=True):
            mismatches.append(
                {
                    "code": "w12e_replay_graph_ref_mismatch",
                    "live_graph_ref": case.get("graph_ref"),
                    "replay_artifact_ref": component.get("artifact_ref"),
                }
            )
    return {
        "status": "fail" if mismatches else "pass",
        "live_graph_count": len(live_graphs),
        "replayed_graph_count": len(replay_graphs),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def _component_blockers(components: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for component in components:
        for blocker in _sequence_of_mappings(component.get("blockers")):
            blockers.append(dict(blocker))
    present_ids = {str(component.get("component_id")) for component in components}
    for component_id in REQUIRED_COMPONENT_IDS:
        if component_id not in present_ids:
            blockers.append(
                _blocker(
                    code="w12e_required_bundle_component_missing",
                    message=f"W12.E required bundle component is absent: {component_id}.",
                    owner="team-runtime-quality",
                    component_id=component_id,
                    capability_label="artifact_missing",
                )
            )
    return blockers


def _packaging_authority_blockers(
    components: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for component in components:
        boundary = _mapping(component.get("authority_boundary"))
        authoritative_for = {
            str(item)
            for item in _sequence(boundary.get("authoritative_for"))
            if str(item)
        }
        leaked = sorted(authoritative_for & FORBIDDEN_PACKAGING_AUTHORITY)
        if leaked:
            blockers.append(
                _blocker(
                    code="w12e_packaging_summary_authority_laundering",
                    message=(
                        "A W12.E package component claims authority that belongs "
                        "to producers, claim evidence, closeout, or public projection."
                    ),
                    owner="team-runtime-quality",
                    component_id=str(component.get("component_id") or "unknown"),
                    leaked_authority=leaked,
                    capability_label="surface_out_of_scope",
                )
            )
    return blockers


def _replay_blockers(replay: Mapping[str, Any]) -> list[dict[str, Any]]:
    if replay.get("status") == "pass":
        return []
    return [
        _blocker(
            code="w12e_replay_evidence_graph_mismatch",
            message="Replay did not see the same evidence graph as the live W12.D path.",
            owner="team-runtime-quality",
            capability_label="verification_missing",
        )
    ]


def _phase_authority_boundary() -> dict[str, Any]:
    return {
        "authoritative_for": ["w12e_bundle_replay_inspection"],
        "may_not_use_for": sorted(FORBIDDEN_PACKAGING_AUTHORITY),
    }


def _component_authority_boundary() -> dict[str, Any]:
    return {
        "authoritative_for": ["bundle_component_presence", "replay_inspection"],
        "may_not_use_for": sorted(FORBIDDEN_PACKAGING_AUTHORITY),
    }


def _blocker(
    *,
    code: str,
    message: str,
    owner: str,
    capability_label: str,
    component_id: str | None = None,
    leaked_authority: Sequence[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "owner": owner,
        "capability_label": capability_label,
        "counts_as_useful_design": False,
        "counts_as_closeout_honesty_failure": False,
        "blocks_rollout_posture": True,
    }
    if component_id is not None:
        payload["component_id"] = component_id
    if leaked_authority is not None:
        payload["leaked_authority"] = list(leaked_authority)
    return payload


def _missing_labels(blockers: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted({str(blocker.get("capability_label")) for blocker in blockers})


def _dedupe_components(
    components: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for component in components:
        component_id = str(component.get("component_id") or "")
        if not component_id:
            continue
        case_id = str(component.get("case_id") or "")
        dedupe_key = f"{component_id}:{case_id}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(dict(component))
    return deduped


def _has_ref(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip()) and value != "missing"
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return any(_has_ref(item) for item in value)
    return value is not None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    return value if isinstance(value, Sequence) and not isinstance(value, str | bytes) else ()


def _sequence_of_mappings(value: object) -> list[Mapping[str, Any]]:
    return [item for item in _sequence(value) if isinstance(item, Mapping)]


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _repo_relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object JSON at {path}")
    return payload


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
