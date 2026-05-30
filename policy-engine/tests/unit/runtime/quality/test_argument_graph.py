from __future__ import annotations

# ruff: noqa: S101
import polisyos.runtime.quality as runtime_quality
from polisyos.pdc import compile_runtime_policy_design_case
from polisyos.runtime.quality.argument_graph import (
    ARGUMENT_GRAPH_EXPORT_SCHEMA_VERSION,
    ARGUMENT_GRAPH_INSPECTION_SCHEMA_VERSION,
    ARGUMENT_GRAPH_SCHEMA_VERSION,
    build_argument_graph,
    build_argument_graph_quality_evidence_surfaces,
    export_argument_graph,
    inspect_argument_graph,
)
from tests._helpers.hds_quality import sha


def test_argument_graph_builder_emits_claim_to_readiness_path_and_exports_profiles() -> None:
    case = _argument_graph_case()

    graph = build_argument_graph(case)

    assert graph["schema_version"] == ARGUMENT_GRAPH_SCHEMA_VERSION
    assert graph["status"] == "pass"
    assert graph["capability_reality_label"] == "implemented"
    assert graph["authority_boundary"]["authoritative_for"] == [
        "argument_graph_structure",
        "warrant_inspection",
    ]
    assert "claim_authority" in graph["authority_boundary"]["may_not_use_for"]

    edge_kinds = [edge["edge_kind"] for edge in graph["edges"]]
    assert edge_kinds == [
        "claim_supported_by_argument",
        "argument_justified_by_warrant",
        "warrant_grounded_in_evidence",
        "evidence_bounded_by_authority",
        "authority_feeds_readiness",
    ]

    warrant = graph["warrants"][0]
    assert warrant["semantics"] == {
        "assumptions": [
            {
                "assumption_id": "assumption.parallel-trends",
                "statement": "Parallel-trends sensitivity remains bounded.",
                "source_refs": [sha("1")],
            }
        ],
        "applicability_predicates": [
            {
                "predicate_id": "applicability.ua-msme",
                "expression": "jurisdiction == 'UA' and population == 'wartime MSMEs'",
                "source_refs": [sha("2")],
            }
        ],
        "confidence_refs": [sha("3")],
        "reliability_refs": [sha("4")],
        "berl_refs": [sha("5")],
        "limits": [
            {
                "limit_id": "limit.no-postwar-extrapolation",
                "statement": "No extrapolation outside wartime credit observations.",
                "severity": "blocking_outside_scope",
                "source_refs": [sha("6")],
            }
        ],
    }

    inspection = inspect_argument_graph(graph)
    assert inspection["schema_version"] == ARGUMENT_GRAPH_INSPECTION_SCHEMA_VERSION
    assert inspection["status"] == "pass"
    assert inspection["summary"]["complete_claim_path_count"] == 1
    assert inspection["warrant_inspection"][0]["machine_inspectable"] is True

    exported = export_argument_graph(graph)
    assert exported["schema_version"] == ARGUMENT_GRAPH_EXPORT_SCHEMA_VERSION
    assert exported["standards"] == ["SACM", "CAE", "GSN"]
    assert exported["claims"][0]["sacm"]["claim"] == "claim-node-rec-1"
    assert exported["claims"][0]["sacm"]["argument_reasoning"] == ["arg-rec-1"]
    assert exported["claims"][0]["sacm"]["asserted_inference"] == ["warrant-rec-1"]
    assert exported["claims"][0]["cae"]["warrant"] == ["warrant-rec-1"]
    assert exported["claims"][0]["gsn"]["solution"] == ["evidence-rec-1"]
    assert exported["claims"][0]["gsn"]["context"] == ["authority-evidence-rec-1"]


def test_argument_graph_rejects_projection_only_authority_for_evidence() -> None:
    case = _argument_graph_case()
    case["evidence_records"][0]["runtime_authority_envelope"].update(
        {
            "authority_role": "projection_only",
            "provenance_kind": "runtime_projection",
        }
    )

    graph = build_argument_graph(case)
    inspection = inspect_argument_graph(graph)

    assert graph["status"] == "blocked"
    assert "argument_graph_evidence_authority_boundary_invalid" in {
        issue["code"] for issue in graph["issues"]
    }
    assert inspection["status"] == "blocked"
    assert inspection["claim_paths"][0]["complete"] is False


def test_argument_graph_blocks_warrant_without_typed_semantics() -> None:
    case = _argument_graph_case()
    warrant = case["warrants"][0]
    warrant["assumptions"] = []
    warrant["applicability_predicates"] = []
    warrant["confidence_refs"] = []
    warrant["reliability_refs"] = []
    warrant["berl_reliability_refs"] = []
    warrant["limits"] = []

    graph = build_argument_graph(case)

    assert graph["status"] == "blocked"
    assert {
        "argument_graph_warrant_assumptions_missing",
        "argument_graph_warrant_applicability_predicates_missing",
        "argument_graph_warrant_confidence_or_reliability_refs_missing",
        "argument_graph_warrant_limits_missing",
    } <= {issue["code"] for issue in graph["issues"]}
    assert inspect_argument_graph(graph)["warrant_inspection"][0]["machine_inspectable"] is False


def test_argument_graph_quality_surfaces_are_runtime_quality_api() -> None:
    graph = build_argument_graph(_argument_graph_case())
    surfaces = build_argument_graph_quality_evidence_surfaces(graph)

    assert runtime_quality.build_argument_graph is build_argument_graph
    assert runtime_quality.inspect_argument_graph is inspect_argument_graph
    assert runtime_quality.export_argument_graph is export_argument_graph
    assert surfaces["argument_graph"] == graph
    assert surfaces["argument_graph_inspection"]["status"] == "pass"
    assert surfaces["argument_graph_export"]["standards"] == ["SACM", "CAE", "GSN"]


def test_argument_graph_builds_from_runtime_pdc_graph_source() -> None:
    runtime_graph = compile_runtime_policy_design_case(
        run_id="run-w8b-runtime-graph",
        job_id="job-w8b-runtime-graph",
        claims=[
            {
                "claim_id": "claim-w8b",
                "claim_type": "recommendation",
                "claim_use": "decision_support",
                "text": "Graph-backed claim has a runtime warrant path.",
                "argument_refs": ["argument:claim-w8b"],
                "warrant_refs": ["warrant:claim-w8b"],
                "limitation_refs": ["limitation:claim-w8b"],
                "accepted_deficit_refs": ["deficit:claim-w8b"],
            }
        ],
        claim_registry={
            "claims": [
                {
                    "claim_id": "claim-w8b",
                    "data_refs": ["data:claim-w8b"],
                    "selected_norm_refs": ["norm:claim-w8b"],
                    "method_output_refs": ["method:claim-w8b"],
                }
            ],
        },
        closeout_verdict={
            "status": "closed",
            "verdict": "can_closeout",
            "can_closeout": True,
        },
    )

    graph = build_argument_graph(runtime_graph.model_dump(mode="json"))
    inspection = inspect_argument_graph(graph)
    exported = export_argument_graph(graph)

    assert graph["status"] == "pass"
    assert graph["summary"]["claim_count"] == 1
    assert graph["summary"]["warrant_count"] == 1
    assert inspection["status"] == "pass"
    assert exported["claims"][0]["cae"]["warrant"] == ["warrant:claim-w8b"]


def _argument_graph_case() -> dict[str, object]:
    return {
        "case_id": "pdc-run-1",
        "run_id": "run-1",
        "job_id": "job-1",
        "tenant_id": "tenant-1",
        "effective_execution_profile": "production",
        "final_major_claims": [
            {
                "claim_id": "rec_1",
                "claim_text": "Targeted credit support is conditionally admissible.",
                "assurance_node_id": "claim-node-rec-1",
                "claim_ref": sha("a"),
                "major": True,
                "argument_refs": ["arg-rec-1"],
                "warrant_refs": ["warrant-rec-1"],
                "evidence_refs": ["evidence-rec-1"],
                "readiness_refs": ["readiness-rec-1"],
            }
        ],
        "arguments": [
            {
                "argument_id": "arg-rec-1",
                "claim_id": "rec_1",
                "strategy": "triangulated_policy_design_case",
                "evidence_refs": ["evidence-rec-1"],
                "warrant_refs": ["warrant-rec-1"],
            }
        ],
        "warrants": [
            {
                "warrant_id": "warrant-rec-1",
                "claim_id": "rec_1",
                "warrant_text": (
                    "Legal, data, method, and scholar evidence jointly bound the claim."
                ),
                "argument_refs": ["arg-rec-1"],
                "evidence_refs": ["evidence-rec-1"],
                "assumptions": [
                    {
                        "assumption_id": "assumption.parallel-trends",
                        "statement": "Parallel-trends sensitivity remains bounded.",
                        "source_refs": [sha("1")],
                    }
                ],
                "applicability_predicates": [
                    {
                        "predicate_id": "applicability.ua-msme",
                        "expression": "jurisdiction == 'UA' and population == 'wartime MSMEs'",
                        "source_refs": [sha("2")],
                    }
                ],
                "confidence_refs": [sha("3")],
                "reliability_refs": [sha("4")],
                "berl_reliability_refs": [sha("5")],
                "limits": [
                    {
                        "limit_id": "limit.no-postwar-extrapolation",
                        "statement": "No extrapolation outside wartime credit observations.",
                        "severity": "blocking_outside_scope",
                        "source_refs": [sha("6")],
                    }
                ],
            }
        ],
        "evidence_records": [
            {
                "evidence_id": "evidence-rec-1",
                "claim_id": "rec_1",
                "evidence_ref": sha("7"),
                "producer_component": "scholar",
                "runtime_event_ref": "event://scholar/support/1",
                "runtime_authority_envelope": {
                    "authority_role": "producer_authority",
                    "provenance_kind": "runtime_emitted",
                    "cas_ref": sha("7"),
                    "runtime_event_ref": "event://scholar/support/1",
                    "authoritative_for": ["evidence_support"],
                    "may_not_use_for": ["projection_authority"],
                },
            }
        ],
        "readiness_records": [
            {
                "readiness_id": "readiness-rec-1",
                "claim_id": "rec_1",
                "status": "publishable",
                "readiness_check": "policy_design_case.argument_graph",
                "authority_refs": ["authority-evidence-rec-1"],
                "blocker_refs": [],
            }
        ],
    }
