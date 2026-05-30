from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from polisyos.pdc import compile_runtime_policy_design_case
from tools.quality.validation import (
    run_policy_design_case_bundle_replay_inspection as w12e,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    REPO_ROOT
    / "architecture/policy_design_case/wave12e_bundle_replay_inspection_manifest.json"
)


def test_w12e_manifest_is_deterministic_and_declares_bundle_contract() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest == w12e.build_w12e_manifest()
    assert manifest["schema_version"] == w12e.MANIFEST_SCHEMA_VERSION
    assert manifest["phase_id"] == "W12.E"
    assert "run_policy_design_case_bundle_replay_inspection.py" in manifest["tool_ref"]
    assert manifest["required_bundle_components"] == list(w12e.REQUIRED_COMPONENT_IDS)
    assert manifest["metric_policy"]["packaging_summaries_are_authority"] is False
    assert "replay_evidence_graph" in manifest["command_contract"]["required_checks"]


def test_w12e_passes_when_bundle_components_and_replay_match() -> None:
    report = w12e.build_w12e_bundle_replay_inspection_report(
        w12d_report=_w12d_report(),
        repo_root=REPO_ROOT,
        w12d_report_ref="repo://_build/.tmp/production-quality/w12d.json",
    )

    assert report["schema_version"] == w12e.SCHEMA_VERSION
    assert report["status"] == "pass"
    assert report["summary"]["required_component_count"] == len(w12e.REQUIRED_COMPONENT_IDS)
    assert report["summary"]["present_component_count"] == len(w12e.REQUIRED_COMPONENT_IDS)
    assert report["summary"]["replay_mismatch_count"] == 0
    assert report["typed_blockers"] == []
    assert {
        component["component_id"] for component in report["bundle"]["components"]
    } == set(w12e.REQUIRED_COMPONENT_IDS)
    assert report["replay_evidence_graph_comparison"]["status"] == "pass"
    assert report["authority_boundary"]["authoritative_for"] == [
        "w12e_bundle_replay_inspection"
    ]
    assert "producer_domain_truth" in report["authority_boundary"]["may_not_use_for"]


def test_w12e_blocks_packaging_summary_authority_laundering() -> None:
    report = w12e.build_w12e_bundle_replay_inspection_report(
        w12d_report=_w12d_report(),
        repo_root=REPO_ROOT,
        w12d_report_ref="repo://_build/.tmp/production-quality/w12d.json",
        extra_components=[
            {
                "component_id": "unsafe_packaging_summary",
                "status": "present",
                "artifact_ref": "repo://_build/.tmp/package-summary.json",
                "authority_boundary": {
                    "authoritative_for": ["producer_domain_truth"],
                    "may_not_use_for": [],
                },
            }
        ],
    )

    assert report["status"] == "blocked"
    assert report["summary"]["packaging_laundering_issue_count"] == 1
    blocker = report["typed_blockers"][0]
    assert blocker["code"] == "w12e_packaging_summary_authority_laundering"
    assert blocker["component_id"] == "unsafe_packaging_summary"
    assert blocker["counts_as_useful_design"] is False
    assert blocker["blocks_rollout_posture"] is True


def test_w12e_uses_w8b_argument_graph_inspection_not_w8a_warrant_counter(
    tmp_path: Path,
) -> None:
    graph_dir = tmp_path / "graphs"
    graph_dir.mkdir()
    graph_path = graph_dir / "case-pass.runtime-pdc-graph.json"
    runtime_graph = compile_runtime_policy_design_case(
        run_id="run-w12e-argument-graph",
        job_id="job-w12e-argument-graph",
        claims=[
            {
                "claim_id": "claim-w12e",
                "claim_type": "recommendation",
                "claim_use": "decision_support",
                "text": "Runtime graph-backed claim has W8.B warrants.",
            }
        ],
        claim_registry={
            "claims": [
                {
                    "claim_id": "claim-w12e",
                    "data_refs": ["data:claim-w12e"],
                    "selected_norm_refs": ["norm:claim-w12e"],
                    "method_output_refs": ["method:claim-w12e"],
                }
            ],
        },
        closeout_verdict={
            "status": "closed",
            "verdict": "can_closeout",
            "can_closeout": True,
        },
    ).model_dump(mode="json")
    graph_path.write_text(json.dumps(runtime_graph), encoding="utf-8")

    report = w12e.build_w12e_bundle_replay_inspection_report(
        w12d_report=_w12d_report(
            artifact_ref="repo://graphs/case-pass.runtime-pdc-graph.json",
            warrant_structure_count=0,
        ),
        repo_root=tmp_path,
        w12d_report_ref="repo://w12d.json",
    )

    assert report["status"] == "pass"
    argument_component = next(
        component
        for component in report["bundle"]["components"]
        if component["component_id"] == "argument_graph"
    )
    assert argument_component["summary"]["warrant_structure_count"] == 0
    assert argument_component["summary"]["argument_graph_inspection_status"] == "pass"
    assert argument_component["summary"]["machine_inspectable_warrant_count"] == 1
    assert not any(
        blocker["code"] == "w12e_argument_graph_warrants_missing"
        for blocker in report["typed_blockers"]
    )


def test_w12e_separates_argument_graph_bridge_from_readiness(
    tmp_path: Path,
) -> None:
    graph_dir = tmp_path / "graphs"
    graph_dir.mkdir()
    graph_path = graph_dir / "case-blocked.runtime-pdc-graph.json"
    runtime_graph = compile_runtime_policy_design_case(
        run_id="run-w12e-readiness-blocked",
        job_id="job-w12e-readiness-blocked",
        claims=[
            {
                "claim_id": "claim-w12e-readiness",
                "claim_type": "recommendation",
                "claim_use": "decision_support",
                "text": "Runtime graph-backed claim has W8.B warrants but blocked readiness.",
            }
        ],
        claim_registry={
            "claims": [
                {
                    "claim_id": "claim-w12e-readiness",
                    "data_refs": ["data:claim-w12e-readiness"],
                    "selected_norm_refs": ["norm:claim-w12e-readiness"],
                    "method_output_refs": ["method:claim-w12e-readiness"],
                }
            ],
        },
        closeout_verdict={
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
        },
    ).model_dump(mode="json")
    graph_path.write_text(json.dumps(runtime_graph), encoding="utf-8")

    report = w12e.build_w12e_bundle_replay_inspection_report(
        w12d_report=_w12d_report(
            artifact_ref="repo://graphs/case-blocked.runtime-pdc-graph.json",
            warrant_structure_count=0,
        ),
        repo_root=tmp_path,
        w12d_report_ref="repo://w12d.json",
    )

    argument_component = next(
        component
        for component in report["bundle"]["components"]
        if component["component_id"] == "argument_graph"
    )
    assert argument_component["summary"]["machine_inspectable_warrant_count"] == 1
    assert argument_component["summary"]["argument_graph_bridge_status"] == "pass"
    assert argument_component["summary"]["argument_graph_readiness_status"] == "blocked"
    assert not any(
        blocker["code"] == "w12e_argument_graph_incomplete"
        for blocker in report["typed_blockers"]
    )


def test_w12e_cli_decorates_existing_w12d_report(tmp_path: Path) -> None:
    input_report = tmp_path / "w12d.json"
    output_report = tmp_path / "w12e.json"
    input_report.write_text(json.dumps(_w12d_report()), encoding="utf-8")

    exit_code = w12e.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--w12d-report",
            str(input_report),
            "--output",
            str(output_report),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_report.read_text(encoding="utf-8"))
    assert payload["phase_id"] == "W12.E"
    assert payload["status"] == "pass"
    assert payload["summary"]["case_count"] == 1


def _w12d_report(
    *,
    artifact_ref: str = "repo://_build/.tmp/pdc-graphs/case-pass.json",
    warrant_structure_count: int = 2,
) -> dict[str, object]:
    return {
        "schema_version": "policyos.policy_design_case.w12d.universal_outcome_corpus.v1",
        "phase_id": "W12.D",
        "status": "pass",
        "summary": {
            "case_count": 1,
            "runtime_useful_design_rate": 1.0,
            "expert_useful_design_ceiling": 1.0,
            "useful_design_alignment_rate": 1.0,
        },
        "cases": [
            {
                "case_id": "case-pass",
                "source_path": "fixture://case-pass",
                "universal_compilation": {
                    "grammar_ref": "grammar:case-pass",
                    "obligation_graph_ref": "obligation-graph:case-pass",
                    "claim_decomposition_ref": "claim-ledger:case-pass",
                    "rule_version_refs": ["obligation-rule:v1"],
                    "tuned_config_refs": ["tuned-config:v1"],
                    "hypothesis_ledger_artifact_ref": "repo://ledgers/case-pass.json",
                },
                "producer_pipeline": {
                    "status": "pass",
                    "producer_pipeline_ref": "producer-pipeline:case-pass",
                    "source_provenance_refs": ["source:case-pass"],
                },
                "runtime_pdc_graph": {
                    "status": "pass",
                    "graph_ref": "sha256:" + "a" * 64,
                    "claim_count": 3,
                    "edge_count": 5,
                    "warrant_structure_count": warrant_structure_count,
                },
                "evidence_bound_pdc_graph": {
                    "artifact_ref": artifact_ref,
                    "authority_boundary": {
                        "authoritative_for": ["pdc_graph_structure"],
                        "may_not_use_for": ["public_projection_authority"],
                    },
                },
                "projection": {"projection_ref": "projection:case-pass"},
                "closeout": {"closeout_ref": "closeout:case-pass"},
                "compatibility": {"compatibility_ref": "compatibility:case-pass"},
            }
        ],
        "typed_blockers": [],
    }
