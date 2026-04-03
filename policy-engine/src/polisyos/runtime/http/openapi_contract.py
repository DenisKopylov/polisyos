"""Public http openapi contract module API."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from polisyos.core.contracts.runtime import RuntimeApiProblem

_ARTIFACT_ID_SAMPLE = "sha256:" + "a" * 64
_RUN_ID_SAMPLE = "R_core_api_001"
_REQUEST_ID_SAMPLE = "req_0123456789abcdef"
_TS_SAMPLE = "2026-02-11T12:00:00Z"
_META_CORE_RUN = {
    "request_id": _REQUEST_ID_SAMPLE,
    "generated_at": _TS_SAMPLE,
    "source_kinds": ["core_run"],
}
_META_NO_SOURCE = {
    "request_id": _REQUEST_ID_SAMPLE,
    "generated_at": _TS_SAMPLE,
    "source_kinds": [],
}

_DEFAULT_PROBLEM_RESPONSES: dict[str, dict[str, str]] = {
    "400": {"code": "bad_request", "description": "Malformed request payload or parameters."},
    "401": {"code": "unauthorized", "description": "Authentication is required for this route."},
    "403": {
        "code": "forbidden",
        "description": "Authenticated principal cannot access this resource.",
    },
    "404": {"code": "not_found", "description": "Requested resource does not exist."},
    "422": {"code": "request_validation_failed", "description": "Request validation failed."},
    "500": {"code": "internal_error", "description": "Unexpected runtime API failure."},
}

_SUCCESS_EXAMPLES_BY_OPERATION: dict[str, dict[str, Any]] = {
    "health": {"status": "ok"},
    "ready": {"status": "ready"},
    "runtime_api_health": {
        "status": "ok",
        "service": "runtime_api_v1",
        "ts": _TS_SAMPLE,
    },
    "get_auth_me": {
        "meta": _META_NO_SOURCE,
        "user_id": "fixture-analyst",
        "display_name": "Fixture Analyst",
        "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "principal_type": "user",
        "cell_id": "cell-a",
        "roles": ["analyst"],
        "permissions": [
            "dashboard.view",
            "evidence.promotions.approve",
            "evidence.promotions.reject",
            "evidence.review",
            "evidence.view",
            "knowledge.view",
            "platform.view",
            "runs.launch",
            "runs.review",
            "runs.view",
        ],
        "mfa_verified": True,
        "feature_overrides": {
            "enableReviewCollaboration": False,
        },
    },
    "list_runs": {
        "meta": _META_CORE_RUN,
        "page": {"limit": 50, "cursor": None, "next_cursor": None, "count": 1, "total": 1},
        "runs": [
            {
                "run_id": _RUN_ID_SAMPLE,
                "source_kind": "core_run",
                "status": "completed",
                "started_at": _TS_SAMPLE,
                "finished_at": _TS_SAMPLE,
                "duration_ms": 4200,
                "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "cell_id": "cell-a",
                "execution_profile": "governed",
                "control_job_id": "job_ctrl_abcdef01",
                "has_trace": True,
                "root_artifact_count": 2,
                "has_workflow_report": True,
                "warnings": [],
                "decision_validity_status": "active",
                "decision_validity_checked_at": _TS_SAMPLE,
                "decision_review_required": False,
                "decision_superseded_by_ref": None,
            }
        ],
    },
    "get_run_details": {
        "meta": _META_CORE_RUN,
        "run": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "status": "completed",
            "started_at": _TS_SAMPLE,
            "finished_at": _TS_SAMPLE,
            "duration_ms": 4200,
            "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "cell_id": "cell-a",
            "execution_profile": "governed",
            "control_job_id": "job_ctrl_abcdef01",
            "has_trace": True,
            "manifest_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "trace_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "capability_manifest_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "root_artifacts": [{"artifact_id": _ARTIFACT_ID_SAMPLE}],
            "has_workflow_report": True,
            "workflow_report_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "warnings": [],
            "decision_validity_status": "active",
            "decision_validity_checked_at": _TS_SAMPLE,
            "decision_review_required": False,
            "decision_superseded_by_ref": None,
        },
    },
    "get_run_timeline": {
        "meta": _META_CORE_RUN,
        "timeline": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "summary": {
                "run_id": _RUN_ID_SAMPLE,
                "total_events": 2,
                "duration_ms": 4200,
                "node_status_counts": {"ok": 1, "fail": 1},
                "phase_counts": {"scientist": 2},
                "cache_hits": 1,
                "cache_stores": 0,
                "cache_bypasses": 1,
            },
            "events": [
                {
                    "index": 0,
                    "timestamp": _TS_SAMPLE,
                    "phase": "scientist",
                    "event": "NODE_OK",
                    "span_id": "span-a",
                    "parent_span_id": None,
                    "input_artifact_ids": [],
                    "output_artifact_ids": [_ARTIFACT_ID_SAMPLE],
                    "metrics": {"duration_ms": 11},
                    "warning_count": 0,
                    "error_count": 0,
                }
            ],
            "notes": [],
        },
    },
    "get_run_nodes": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "source_kind": "core_run",
        "nodes": [
            {
                "alias": "run_governance",
                "node_id": "scientist.node_run_governance@1.2.0",
                "status": "fail",
                "duration_ms": 7,
                "error_code": "governance.blocked",
                "error_message": "Blocked by policy",
                "error_details": {"severity": "blocker"},
                "skip_reason": None,
                "artifact_ids": [_ARTIFACT_ID_SAMPLE],
                "input_artifact_ids": [],
                "output_artifact_ids": [_ARTIFACT_ID_SAMPLE],
            }
        ],
    },
    "get_run_lineage": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "lineage": {
            "root_artifact_ids": [_ARTIFACT_ID_SAMPLE],
            "total_nodes": 1,
            "total_edges": 0,
            "total_size_bytes": 1024,
            "is_complete": True,
            "missing_artifact_ids": [],
            "corrupted_artifact_ids": [],
            "nodes": [
                {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "role": "root",
                    "kind": "scientist.workflow_report",
                    "status": "ok",
                    "byte_size": 1024,
                    "depth": 0,
                }
            ],
            "edges": [],
        },
    },
    "get_run_evidence_context": {
        "meta": _META_CORE_RUN,
        "context": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "execution_plan_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "evidence_bundle_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "data_snapshot_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "input_bindings_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "related_artifacts": [{"artifact_id": _ARTIFACT_ID_SAMPLE}],
            "data_needs": [
                {
                    "need_id": "need_1",
                    "metric": "macro.gdp.real",
                    "geography": "USA",
                    "time_start": "2019",
                    "time_end": "2024",
                    "granularity": "annual",
                    "quality_min": 0.75,
                    "purpose": "policy_drafting",
                    "matched_plan_ids": ["plan_fixture_fetch_001"],
                }
            ],
            "fetch_plans": [
                {
                    "plan_id": "plan_fixture_fetch_001",
                    "metric_id": "macro.gdp.real",
                    "connector_id": "worldbank.wdi",
                    "dataset_id": "NY.GDP.MKTP.KD",
                    "profile_id": "worldbank_wdi",
                    "source_lane": "fastlane",
                    "matched_need_ids": ["need_1"],
                    "metadata": {},
                }
            ],
            "promotion_candidates": [
                {
                    "promotion_id": "promotion_fixture_001",
                    "metric_id": "macro.gdp.real",
                    "connector_id": "worldbank.wdi",
                    "dataset_id": "NY.GDP.MKTP.KD",
                    "profile_id": "worldbank_wdi",
                    "source_lane": "explorelane",
                    "confidence": 0.87,
                    "status": "pending",
                    "created_at": _TS_SAMPLE,
                    "signals": ["new_source", "coverage_gap_closed"],
                    "matched_plan_id": "plan_fixture_fetch_001",
                    "metadata": {},
                }
            ],
            "warnings": [],
        },
    },
    "get_run_agents": {
        "meta": _META_CORE_RUN,
        "pipeline": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "total_attempts": 1,
            "latest_verdict": "NEEDS_REVISION",
            "attempts": [
                {
                    "attempt": 1,
                    "status": "failed",
                    "verdict": "abort_with_report",
                    "started_at": _TS_SAMPLE,
                    "finished_at": _TS_SAMPLE,
                    "duration_ms": 3,
                    "steps": [
                        {
                            "attempt": 1,
                            "agent": "pi_agent",
                            "action": "problem_frame_created",
                            "status": "ok",
                            "timestamp": _TS_SAMPLE,
                            "summary": "Problem framed",
                            "details": {},
                            "prompt": None,
                            "response": None,
                            "model": None,
                            "latency_ms": None,
                            "token_usage": {},
                        },
                        {
                            "attempt": 1,
                            "agent": "critic",
                            "action": "critique_complete",
                            "status": "warn",
                            "timestamp": _TS_SAMPLE,
                            "summary": "NEEDS_REVISION",
                            "details": {"verdict": "NEEDS_REVISION"},
                            "prompt": None,
                            "response": None,
                            "model": "gpt-4.1-mini",
                            "provider": "gateway",
                            "model_variant_id": "gpt_4_1_mini_1",
                            "latency_ms": 1480,
                            "cost_usd": 0.00145,
                            "token_usage": {"prompt_tokens": 411, "completion_tokens": 92, "total_tokens": 503},
                        },
                    ],
                    "notes": [],
                }
            ],
            "decision_packet_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "reflexion_terminal_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "execution_plan_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "method_catalog_snapshot_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "preflight": {
                "ready_to_run": True,
                "diagnostics": [],
                "notes": [],
                "report_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            },
            "evaluator": {
                "verdict": "APPROVE",
                "scores": {
                    "kpi_score": 0.9,
                    "uncertainty_score": 0.8,
                    "constraints_score": 1.0,
                    "data_quality_score": 0.85,
                    "budget_score": 0.92,
                    "total_score": 0.89,
                },
                "reasons": ["critic_verdict:APPROVE"],
                "replanning_hints": [],
                "diagnostics": [],
                "notes": [],
                "report_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            },
            "iteration_lifecycle": {
                "iteration": 1,
                "state": "approved",
                "stop_reason": "approved",
                "last_verdict": "APPROVE",
                "state_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
                "notes": [],
            },
            "reproducibility": {
                "seed": 0,
                "seed_source": "params.random_seed",
                "determinism_tier": "strict_cpu",
                "plan_hash": "sha256:planhash",
                "registry_hash": "sha256:registryhash",
                "method_catalog_hash": "sha256:cataloghash",
                "data_snapshot_hash": "sha256:datasnapshothash",
                "input_bindings_hash": "sha256:bindingshash",
                "readiness": "partial",
                "why_partial": ["missing_optional_inputs"],
                "missing_refs": ["input_bindings_ref", "knowledge_bundle_ref"],
                "suggested_next_step": "Persist input_bindings_ref for replay-grade completeness.",
                "manifest_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
                "notes": [],
            },
            "source": "decision_packet.audit_trail",
            "notes": [],
        },
    },
    "get_run_workflow": {
        "meta": _META_CORE_RUN,
        "workflow": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "summary": {
                "workflow_id": "scientist_default",
                "error_policy": "fail_fast",
                "status": "fail",
                "node_count": 2,
                "edge_count": 1,
                "ok_count": 1,
                "skip_count": 0,
                "fail_count": 1,
                "max_depth": 1,
                "critical_path_duration_ms": 18,
            },
            "nodes": [
                {
                    "alias": "compile_foundry",
                    "node_id": "scientist.node_compile_foundry@1.0.0",
                    "depends_on": [],
                    "depth": 0,
                    "status": "ok",
                    "duration_ms": 11,
                    "error_code": None,
                    "error_message": None,
                    "artifact_ids": [_ARTIFACT_ID_SAMPLE],
                    "input_artifact_ids": [],
                    "output_artifact_ids": [_ARTIFACT_ID_SAMPLE],
                    "heat": 0.611,
                },
                {
                    "alias": "run_governance",
                    "node_id": "scientist.node_run_governance@1.2.0",
                    "depends_on": ["compile_foundry"],
                    "depth": 1,
                    "status": "fail",
                    "duration_ms": 7,
                    "error_code": "governance.blocked",
                    "error_message": "Blocked by policy",
                    "artifact_ids": [_ARTIFACT_ID_SAMPLE],
                    "input_artifact_ids": [],
                    "output_artifact_ids": [_ARTIFACT_ID_SAMPLE],
                    "heat": 0.389,
                },
            ],
            "edges": [
                {
                    "from_alias": "compile_foundry",
                    "to_alias": "run_governance",
                }
            ],
            "workflow_spec_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "workflow_report_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "notes": [],
        },
    },
    "get_node_debug": {
        "meta": _META_CORE_RUN,
        "debug": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "alias": "run_governance",
            "record": {
                "alias": "run_governance",
                "node_id": "scientist.node_run_governance@1.2.0",
                "status": "fail",
                "duration_ms": 7,
                "error_code": "governance.blocked",
                "error_message": "Blocked by policy",
                "error_details": {"severity": "blocker"},
                "skip_reason": None,
                "artifact_ids": [_ARTIFACT_ID_SAMPLE],
                "input_artifact_ids": [],
                "output_artifact_ids": [_ARTIFACT_ID_SAMPLE],
            },
            "timeline_events": [],
            "cache_hits": 0,
            "cache_stores": 0,
            "cache_bypasses": 1,
            "notes": [],
        },
    },
    "get_governance_debug": {
        "meta": _META_CORE_RUN,
        "debug": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "verdict": "reject",
            "issues": [{"code": "GOV001", "message": "Policy blocker"}],
            "issue_summary": {"blocker_count": 0, "warning_count": 0, "info_count": 0},
            "notes": ["manual review required"],
            "report_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "report_kind": "scientist.governance_report",
            "report_schema_version": "1.0",
            "legal_executed": False,
            "transport_summary": {
                "status": "identified",
                "transport_mode": "transport_formula",
                "identification_engine": "simplified_legacy",
                "requires_expert_review": False,
                "data_gaps_count": 0,
            },
            "validation_trace": {"total_blockers": 1},
            "decision_validity": {
                "status": "requires_human_review",
                "checked_at": _TS_SAMPLE,
                "reasons": ["human_or_expert_review_required"],
                "triggers": [
                    {
                        "trigger_type": "expert_review",
                        "status": "requires_human_review",
                        "reason": "human_or_expert_review_required",
                    }
                ],
                "review_required": True,
                "evaluation_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
                "superseded_by_ref": None,
                "recommended_action": "human_review",
                "decision_lineage_key": "sha256:lineage",
            },
            "normative_summary": {
                "selected_policy": "weighted_welfare",
                "selected_option": "baseline",
                "model_completeness": "partial",
                "residual_dissent_count": 1,
                "rights_violation_count": 0,
                "winners": ["owners"],
                "losers": ["workers"],
            },
            "normative_arbitration_result_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "fallback_from_decision_packet": False,
        },
    },
    "get_run_errors": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "errors": [
            {
                "source": "workflow_report",
                "code": "governance.blocked",
                "message": "Blocked by policy",
                "node_alias": "run_governance",
                "timestamp": _TS_SAMPLE,
                "details": {"severity": "blocker"},
            }
        ],
    },
    "get_run_feedback": {
        "meta": _META_CORE_RUN,
        "feedback": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "decision_packet_ref": {
                "artifact_id": _ARTIFACT_ID_SAMPLE,
                "kind": "scientist.decision_packet",
                "media_type": "application/json",
            },
            "feedback_loop": {
                "anchor_at": _TS_SAMPLE,
                "monitoring_contract_ref": {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "kind": "scientist.decision_monitoring_contract",
                    "media_type": "application/json",
                },
                "latest_monitoring_report_ref": {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "kind": "scientist.decision_monitoring_report",
                    "media_type": "application/json",
                },
                "latest_compare_report_ref": {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "kind": "scientist.decision_compare_report",
                    "media_type": "application/json",
                },
                "latest_reissue_plan_ref": {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "kind": "scientist.decision_reissue_plan",
                    "media_type": "application/json",
                },
                "backtest_mode_effective": "scientist",
                "backtest_trust_eligible": True,
            },
            "monitoring_contract": {
                "schema_version": "1.0",
                "run_id": _RUN_ID_SAMPLE,
                "decision_lineage_key": "decision-lineage-fixture",
                "anchor_at": _TS_SAMPLE,
                "backtest_mode_effective": "scientist",
                "backtest_trust_eligible": True,
                "metrics": [
                    {
                        "metric_id": "employment_rate",
                        "source_metric_id": "employment_rate",
                        "baseline_value": 0.61,
                        "confirm_range": {"lower": 0.58, "upper": 0.64},
                        "refute_range": {"lower": 0.55, "upper": 0.67},
                        "window": {
                            "start_offset_days": 0,
                            "end_offset_days": 30,
                            "grace_days": 7,
                        },
                        "min_observations": 1,
                        "weight": 1.0,
                        "recalibration_target": True,
                        "metadata": {},
                    }
                ],
                "notes": [],
            },
            "monitoring_report": {
                "schema_version": "1.0",
                "run_id": _RUN_ID_SAMPLE,
                "decision_packet_ref": _ARTIFACT_ID_SAMPLE,
                "monitoring_contract_ref": _ARTIFACT_ID_SAMPLE,
                "anchor_at": _TS_SAMPLE,
                "evaluated_at": _TS_SAMPLE,
                "overall_verdict": "refuted",
                "metrics": [
                    {
                        "metric_id": "employment_rate",
                        "source_metric_id": "employment_rate",
                        "baseline_value": 0.61,
                        "actual_value": 0.52,
                        "observed_count": 3,
                        "verdict": "refuted",
                        "reason": "actual_value_outside_refute_range",
                        "delta": -0.09,
                        "recalibration_target": True,
                        "metadata": {},
                    }
                ],
                "refuted_metric_ids": ["employment_rate"],
                "degraded_reasons": [],
                "notes": [],
            },
            "compare_report": {
                "schema_version": "1.0",
                "left_run_id": _RUN_ID_SAMPLE,
                "right_run_id": _RUN_ID_SAMPLE,
                "left_decision_packet_ref": _ARTIFACT_ID_SAMPLE,
                "right_decision_packet_ref": _ARTIFACT_ID_SAMPLE,
                "deltas": {
                    "outcome": {
                        "changed": True,
                        "refs": {},
                        "summary": {"refuted_metric_ids": ["employment_rate"]},
                        "details": {"overall_verdict": "refuted"},
                    },
                    "law": {"changed": False, "refs": {}, "summary": {}, "details": {}},
                    "data": {"changed": False, "refs": {}, "summary": {}, "details": {}},
                    "evidence": {"changed": False, "refs": {}, "summary": {}, "details": {}},
                    "model": {"changed": False, "refs": {}, "summary": {}, "details": {}},
                    "governance": {"changed": False, "refs": {}, "summary": {}, "details": {}},
                },
                "root_cause": ["outcome"],
                "notes": [],
            },
            "reissue_plan": {
                "schema_version": "1.0",
                "source_run_id": _RUN_ID_SAMPLE,
                "source_decision_packet_ref": _ARTIFACT_ID_SAMPLE,
                "monitoring_report_ref": _ARTIFACT_ID_SAMPLE,
                "compare_report_ref": _ARTIFACT_ID_SAMPLE,
                "calibration_config_ref": _ARTIFACT_ID_SAMPLE,
                "parameter_override_bundle_ref": _ARTIFACT_ID_SAMPLE,
                "refuted_metric_ids": ["employment_rate"],
                "revised_metric_ids": [],
                "publication_mode": "human_gated",
                "requires_operator_confirmation": True,
                "recommended_action": "reissue_decision_packet",
                "notes": [],
            },
            "decision_validity": {
                "status": "requires_human_review",
                "checked_at": _TS_SAMPLE,
                "reasons": ["post_deployment_refutation_detected"],
                "triggers": [
                    {
                        "trigger_type": "post_deployment_refutation",
                        "status": "requires_human_review",
                        "reason": "post_deployment_refutation_detected",
                    }
                ],
                "review_required": True,
                "evaluation_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
                "superseded_by_ref": None,
                "recommended_action": "human_review",
                "decision_lineage_key": "decision-lineage-fixture",
            },
            "notes": [],
        },
    },
    "get_run_compare": {
        "meta": _META_CORE_RUN,
        "compare": {
            "left_run_id": "R_core_api_001",
            "right_run_id": "R_core_api_002",
            "report": {
                "schema_version": "1.0",
                "left_run_id": "R_core_api_001",
                "right_run_id": "R_core_api_002",
                "left_decision_packet_ref": _ARTIFACT_ID_SAMPLE,
                "right_decision_packet_ref": "sha256:" + "b" * 64,
                "deltas": {
                    "law": {
                        "changed": True,
                        "refs": {
                            "left_norm_pack_ref": _ARTIFACT_ID_SAMPLE,
                            "right_norm_pack_ref": "sha256:" + "b" * 64,
                        },
                        "summary": {"changed_norm_ids": ["art.12"]},
                        "details": {"selected_policy_changed": False},
                    },
                    "data": {"changed": False, "refs": {}, "summary": {}, "details": {}},
                    "evidence": {"changed": False, "refs": {}, "summary": {}, "details": {}},
                    "model": {"changed": False, "refs": {}, "summary": {}, "details": {}},
                    "governance": {"changed": False, "refs": {}, "summary": {}, "details": {}},
                    "outcome": {"changed": False, "refs": {}, "summary": {}, "details": {}},
                },
                "root_cause": ["law"],
                "notes": [],
            },
        },
    },
    "get_artifact_manifest": {
        "meta": _META_NO_SOURCE,
        "artifact": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.workflow_report",
            "media_type": "application/json",
            "byte_size": 1024,
            "created_at": _TS_SAMPLE,
            "schema_name": "scientist.workflow_report",
            "schema_version": "1.0",
            "producer_component": "scientist.run_governance",
            "producer_version": "1.0.0",
            "inputs": [],
            "integrity_sha256": "a" * 64,
        },
    },
    "get_artifact_content": {
        "meta": _META_NO_SOURCE,
        "artifact": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.workflow_report",
            "media_type": "application/json",
            "mode": "json",
            "size_bytes": 1024,
            "max_bytes": 4096,
            "truncated": False,
            "preview": {"status": "fail"},
        },
    },
    "get_artifact_lineage": {
        "meta": _META_NO_SOURCE,
        "lineage": {
            "root_artifact_ids": [_ARTIFACT_ID_SAMPLE],
            "total_nodes": 1,
            "total_edges": 0,
            "total_size_bytes": 1024,
            "is_complete": True,
            "missing_artifact_ids": [],
            "corrupted_artifact_ids": [],
            "nodes": [
                {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "role": "root",
                    "kind": "scientist.workflow_report",
                    "status": "ok",
                    "byte_size": 1024,
                    "depth": 0,
                }
            ],
            "edges": [],
        },
    },
    "get_artifact_schema": {
        "meta": _META_NO_SOURCE,
        "schema": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.workflow_report",
            "media_type": "application/json",
            "schema_name": "scientist.workflow_report",
            "schema_version": "1.0",
            "top_level_keys": ["run_id", "status", "nodes"],
        },
    },
    # --- Control-plane operations ---
    "launch_run": {
        "meta": _META_NO_SOURCE,
        "status": "accepted",
        "run_id": "R_ctrl_abcdef01",
        "job_id": "job_ctrl_abcdef01",
        "effective_execution_profile": "dev",
        "message": "Workflow run R_ctrl_abcdef01 accepted and queued for durable execution.",
    },
    "evaluate_run_feedback": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "action": "evaluate_feedback",
        "status": "completed",
        "monitoring_report_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.decision_monitoring_report",
            "media_type": "application/json",
        },
        "compare_report_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.decision_compare_report",
            "media_type": "application/json",
        },
        "reissue_plan_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.decision_reissue_plan",
            "media_type": "application/json",
        },
        "reissued_run_id": None,
        "message": "Feedback evaluation for run R_core_api_001 completed.",
    },
    "launch_nl_run": {
        "meta": _META_NO_SOURCE,
        "status": "accepted",
        "run_id": "R_nl_abcdef02",
        "job_id": "job_nl_abcdef02",
        "effective_execution_profile": "dev",
        "message": "Natural-language run R_nl_abcdef02 accepted. Agent circuit was queued in mock mode: mock agents.",
    },
    "reissue_run": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "action": "reissue",
        "status": "accepted",
        "monitoring_report_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.decision_monitoring_report",
            "media_type": "application/json",
        },
        "compare_report_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.decision_compare_report",
            "media_type": "application/json",
        },
        "reissue_plan_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.decision_reissue_plan",
            "media_type": "application/json",
        },
        "reissued_run_id": "R_ctrl_reissue_003",
        "message": "Reissue for run R_core_api_001 accepted.",
    },
    "get_control_job_status": {
        "meta": _META_NO_SOURCE,
        "job_id": "job_nl_abcdef02",
        "kind": "natural_language_run",
        "state": "running",
        "run_id": "R_nl_abcdef02",
        "pipeline_id": None,
        "requested_execution_profile": None,
        "effective_execution_profile": "dev",
        "capability_manifest_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
        "submitted_at": _TS_SAMPLE,
        "started_at": _TS_SAMPLE,
        "finished_at": None,
        "error_message": None,
        "progress": {},
    },
    "get_control_capabilities": {
        "meta": _META_NO_SOURCE,
        "runtime_api_version": "1.0.0",
        "shell_flavor": "atlas",
        "default_locale": "en",
        "supported_locales": ["en", "uk"],
        "default_execution_profile": "dev",
        "supported_execution_profiles": ["dev", "research", "governed", "production"],
        "worker_backend": "embedded",
        "state_store_backend": "sqlite",
        "security_posture": {"required": False, "middleware_required": False, "authz_shadow_allowed": True},
        "fallback_rules": {"mock_fallback_allowed": True, "policy_flag_required_for_mock_fallback": False},
        "workspaces": [
            "command_center",
            "scenario_composer",
            "runs_decisions",
            "evidence_fabric",
            "lex_knowledge",
            "platform_health",
        ],
        "features": [
            {
                "key": "natural_language_runs",
                "label": "Natural-language runs",
                "description": "Use the agent circuit to transform NL requests into executable policy runs.",
                "category": "runs",
                "enabled": True,
                "stage": "active",
            },
            {
                "key": "required_preflight",
                "label": "Required preflight",
                "description": "Run execution-plan preflight diagnostics before execution.",
                "category": "governance",
                "enabled": True,
                "stage": "active",
            },
            {
                "key": "security_admin_layer",
                "label": "Security / admin layer",
                "description": "Dedicated tenant/authz/audit admin surfaces.",
                "category": "platform",
                "enabled": False,
                "stage": "deferred",
            },
        ],
        "constraints": {
            "max_parallel_models": 16,
            "max_nl_iterations": 10,
            "artifact_preview_max_bytes": 2000000,
            "task_runner": "durable_control_worker",
            "default_locale": "en",
            "supported_locales": ["en", "uk"],
        },
    },
    "ingest_data": {
        "meta": _META_NO_SOURCE,
        "status": "completed",
        "evidence_bundle_ref": _ARTIFACT_ID_SAMPLE,
        "datasets_fetched": 2,
        "message": "Successfully ingested 2 dataset(s).",
    },
    "resolve_data_needs": {
        "meta": _META_NO_SOURCE,
        "mode": "hybrid",
        "fetch_plans": [
            {
                "plan_id": "plan_usa_gdp",
                "metric_id": "us.macro.gdp_nominal",
                "connector_id": "worldbank.wdi",
                "dataset_id": "NY.GDP.MKTP.CD",
                "profile_id": "worldbank_wdi",
                "filters": {"country": ["USA"]},
                "date_start": "2015",
                "date_end": "2024",
                "granularity": "annual",
                "quality_min": 0.75,
                "source_lane": "fastlane",
                "persist_payload": False,
                "max_preview_rows": 20,
                "fallbacks": [
                    {
                        "connector_id": "sdmx.source",
                        "dataset_id": "OECD:QNA_GDP",
                        "profile_id": "oecd_sdmx",
                        "filters": {},
                    }
                ],
                "metadata": {},
            }
        ],
        "candidates": [
            {
                "candidate_id": "cand_usa_gdp_1",
                "metric_id": "us.macro.gdp_nominal",
                "connector_id": "worldbank.wdi",
                "dataset_id": "NY.GDP.MKTP.CD",
                "profile_id": "worldbank_wdi",
                "source_lane": "fastlane",
                "confidence": 0.91,
                "rank": 1,
                "trust_score": 0.95,
                "freshness_score": 0.8,
                "coverage_estimate": 0.88,
                "latency_estimate_ms": 320,
                "filters_template": {"country": ["{ISO3}"]},
                "match_reason": "exact_metric_binding",
                "metadata": {},
            }
        ],
        "warnings": [],
    },
    "discover_data_sources": {
        "meta": _META_NO_SOURCE,
        "candidates": [
            {
                "candidate_id": "disc_usa_unemployment_1",
                "metric_id": "us.macro.unemployment_rate",
                "connector_id": "sdmx.source",
                "dataset_id": "ILO:UNE_DEAP_Q",
                "dataset_name": "Unemployment rate",
                "description": "Quarterly unemployment rate by country.",
                "profile_id": "ilo_sdmx",
                "source_lane": "explorelane",
                "confidence": 0.76,
                "coverage_estimate": 0.72,
                "latency_estimate_ms": 540,
                "schema_excerpt": {"dimensions": ["country", "time"]},
                "discovered_at": _TS_SAMPLE,
                "metadata": {},
            }
        ],
        "docs_fetched_total": 9,
        "index_stats": {
            "index_docs_total": 9,
            "index_size_bytes": 40960,
            "indexed_sources": 2,
            "docs_added_last_run": 9,
            "source_coverage": {"sdmx.source": 6, "worldbank.wdi": 3},
            "last_updated": _TS_SAMPLE,
        },
        "warnings": [],
    },
    "preview_fetch_plan": {
        "meta": _META_NO_SOURCE,
        "preview": {
            "status": "ok",
            "connector_id": "worldbank.wdi",
            "dataset_id": "NY.GDP.MKTP.CD",
            "row_count": 10,
            "completeness": 0.87,
            "coverage_ok": True,
            "quality_min": 0.75,
            "sample_rows": [{"country": "USA", "year": 2023, "value": 27360935}],
            "schema": {"schema_id": "wdi.v1", "schema_version": "1"},
            "quality_flags": [],
            "message": None,
            "latency_ms": 281,
        },
    },
    "search_data_catalog": {
        "meta": _META_NO_SOURCE,
        "query": "gdp*",
        "matches": [
            {
                "candidate_id": "cand_usa_gdp_1",
                "metric_id": "us.macro.gdp_nominal",
                "connector_id": "worldbank.wdi",
                "dataset_id": "NY.GDP.MKTP.CD",
                "profile_id": "worldbank_wdi",
                "source_lane": "fastlane",
                "confidence": 0.91,
                "rank": 1,
                "trust_score": 0.95,
                "freshness_score": 0.8,
                "coverage_estimate": 0.88,
                "latency_estimate_ms": 320,
                "filters_template": {"country": ["{ISO3}"]},
                "match_reason": "catalog_query_match",
                "metadata": {},
            }
        ],
        "total_matches": 1,
    },
    "get_data_index_stats": {
        "meta": _META_NO_SOURCE,
        "stats": {
            "index_docs_total": 29,
            "index_size_bytes": 121344,
            "indexed_sources": 4,
            "docs_added_last_run": 9,
            "source_coverage": {"worldbank.wdi": 10, "sdmx.source": 19},
            "last_updated": _TS_SAMPLE,
        },
    },
    "list_data_promotion_candidates": {
        "meta": _META_NO_SOURCE,
        "candidates": [
            {
                "promotion_id": "promo_01",
                "metric_id": "us.macro.unemployment_rate",
                "connector_id": "sdmx.source",
                "dataset_id": "ILO:UNE_DEAP_Q",
                "profile_id": "ilo_sdmx",
                "source_lane": "explorelane",
                "confidence": 0.83,
                "signals": ["high_completeness", "stable_latency"],
                "status": "pending",
                "created_at": _TS_SAMPLE,
                "metadata": {},
            }
        ],
    },
    "approve_data_promotion": {
        "meta": _META_NO_SOURCE,
        "promotion_id": "promo_01",
        "status": "approved",
        "message": "Promotion candidate approved and source bindings updated.",
        "binding_updated": True,
    },
    "reject_data_promotion": {
        "meta": _META_NO_SOURCE,
        "promotion_id": "promo_01",
        "status": "rejected",
        "message": "Promotion candidate rejected.",
        "binding_updated": False,
    },
    "list_connectors": {
        "meta": _META_NO_SOURCE,
        "connectors": [
            {
                "connector_id": "worldbank.wdi",
                "namespace": "worldbank",
                "version": "1.0.0",
                "known_datasets": ["NY.GDP.MKTP.CD", "SP.POP.TOTL"],
                "loaded": True,
                "last_health_check": None,
            },
        ],
    },
    "list_source_profiles": {
        "meta": _META_NO_SOURCE,
        "profiles": [
            {
                "profile_id": "worldbank_wdi",
                "display_name": "World Bank WDI",
                "description": "World Development Indicators via World Bank API v2",
                "connector_family": "worldbank",
                "base_url": "https://api.worldbank.org/v2",
                "auth_policy": "none",
                "tags": ["international", "development", "gdp"],
                "source_organization": "The World Bank Group",
                "estimated_datasets": 1600,
                "connector_available": True,
            }
        ],
    },
    "list_binding_profiles": {
        "meta": _META_NO_SOURCE,
        "profiles": [
            {
                "profile_id": "macro.default",
                "display_name": "Macro default mapping",
                "description": "Default metric-to-column binding rules.",
                "schema_family": "timeseries",
                "strategy": "auto",
                "rule_count": 7,
                "expected_columns": ["country", "year", "value"],
                "tags": ["macro", "default"],
            }
        ],
    },
    "list_llm_profiles": {
        "meta": _META_NO_SOURCE,
        "profiles": [
            {
                "profile_id": "gpt5_mini_gateway",
                "display_name": "GPT-5 mini (Gateway)",
                "description": "Balanced OpenAI frontier model via OpenAI-compatible gateway.",
                "provider": "openai",
                "model_id": "gpt-5-mini",
                "base_url": "https://api.gonkagate.com/v1",
                "tags": ["frontier", "balanced"],
                "capabilities": ["json", "tool_calling"],
                "input_cost_per_mtoken_usd": None,
                "output_cost_per_mtoken_usd": None,
                "enabled": True,
            }
        ],
    },
    "get_cache_status": {
        "meta": _META_NO_SOURCE,
        "total_entries": 0,
        "total_size_bytes": 0,
        "entries": [],
    },
    "trigger_lex_pipeline": {
        "meta": _META_NO_SOURCE,
        "status": "accepted",
        "pipeline_id": "lex_a1b2c3d4e5f6",
        "job_id": "job_lex_a1b2c3d4e5f6",
        "effective_execution_profile": "dev",
        "message": "Pipeline lex_a1b2c3d4e5f6 launched with stages: graph, parse, spo, structure",
    },
    "get_lex_pipeline_status": {
        "meta": _META_NO_SOURCE,
        "pipeline_id": "lex_a1b2c3d4e5f6",
        "state": "running",
        "progress_summary": {"structured": 5000, "spo_extracted": 2300},
        "error_message": None,
    },
    "get_lex_graph_stats": {
        "meta": _META_NO_SOURCE,
        "total_entities": 12450,
        "total_facts": 87300,
        "total_provisions": 45200,
        "top_predicates": [
            {"predicate": "regulates", "count": 12000},
            {"predicate": "defines", "count": 8500},
        ],
        "top_entity_types": [
            {"entity_type": "concept", "count": 9200},
            {"entity_type": "institution", "count": 2100},
        ],
        "db_exists": True,
    },
    "search_lex_graph": {
        "meta": _META_NO_SOURCE,
        "query": "бюджетний дефіцит",
        "results": [
            {
                "fact_id": "a1b2c3d4e5f6g7h8i9j0",
                "subject_name": "budget_deficit_limit",
                "predicate": "must_not_exceed",
                "object_name": "3_percent_of_gdp",
                "fact_text": "Budget deficit must not exceed 3% of projected GDP",
                "confidence": 0.92,
                "norm_type": "obligation",
                "doc_name": "Бюджетний кодекс України",
                "doc_reestr_code": "21010",
                "provision_citation": "Стаття 14, пункт 2",
            }
        ],
        "total": 1,
    },
    "list_control_workers": {
        "meta": _META_NO_SOURCE,
        "active_only": True,
        "workers": [
            {
                "worker_id": "worker_embedded_001",
                "worker_type": "embedded",
                "state": "idle",
                "active_job_id": None,
                "metadata": {},
                "heartbeat_at": _TS_SAMPLE,
                "lease_expires_at": _TS_SAMPLE,
                "created_at": _TS_SAMPLE,
                "updated_at": _TS_SAMPLE,
            }
        ],
    },
    "list_control_outbox": {
        "meta": _META_NO_SOURCE,
        "state": "pending",
        "limit": 100,
        "events": [
            {
                "event_id": "evt_outbox_001",
                "topic": "decision_validity",
                "event_key": "R_core_api_001",
                "state": "pending",
                "job_id": "job_ctrl_abcdef01",
                "run_id": _RUN_ID_SAMPLE,
                "payload": {},
                "created_at": _TS_SAMPLE,
                "published_at": None,
                "attempt": 0,
                "error_message": None,
            }
        ],
    },
    "publish_decision_validity_event": {
        "meta": _META_NO_SOURCE,
        "event_id": "evt_dv_001",
        "dedupe_key": "dv_data_update_2026-02-11",
        "affected_packets": [_ARTIFACT_ID_SAMPLE],
        "affected_statuses": {"invalidated": 1},
        "message": "Decision validity event published; 1 packet(s) affected.",
    },
    "get_run_decision_validity": {
        "meta": _META_NO_SOURCE,
        "run_id": _RUN_ID_SAMPLE,
        "decision_packet_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.decision_packet",
            "media_type": "application/json",
        },
        "status": "active",
        "checked_at": _TS_SAMPLE,
        "reasons": [],
        "triggers": [],
        "review_required": False,
        "supersedes_decision_ref": None,
        "superseded_by_ref": None,
        "evaluation_ref": None,
        "decision_lineage_key": "lineage_R_core_api_001",
        "recommended_action": "none",
        "lifecycle": {
            "events": [],
            "transitions": [],
            "pending_reviews": [],
            "scheduled_jobs": [],
            "reissue_candidates": [],
            "latest_transition_at": None,
        },
    },
    "get_packet_decision_validity": {
        "meta": _META_NO_SOURCE,
        "run_id": None,
        "decision_packet_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.decision_packet",
            "media_type": "application/json",
        },
        "status": "active",
        "checked_at": _TS_SAMPLE,
        "reasons": [],
        "triggers": [],
        "review_required": False,
        "supersedes_decision_ref": None,
        "superseded_by_ref": None,
        "evaluation_ref": None,
        "decision_lineage_key": "lineage_pkt_001",
        "recommended_action": "none",
        "lifecycle": {
            "events": [],
            "transitions": [],
            "pending_reviews": [],
            "scheduled_jobs": [],
            "reissue_candidates": [],
            "latest_transition_at": None,
        },
    },
}


def _problem_example(*, status_code: int, code: str, path: str) -> dict[str, Any]:
    return {
        "type": "about:blank",
        "title": code.replace("_", " ").capitalize(),
        "status": status_code,
        "detail": f"{code} while processing request.",
        "code": code,
        "instance": path,
        "request_id": _REQUEST_ID_SAMPLE,
        "error": code,
        "status_code": status_code,
    }


def _iter_operations(schema: dict[str, Any]):
    paths = schema.get("paths")
    if not isinstance(paths, dict):
        return
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post"}:
                continue
            if not isinstance(operation, dict):
                continue
            yield path, method.lower(), operation


def augment_runtime_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    """Augment runtime openapi helper."""
    mutated = deepcopy(schema)
    components = mutated.setdefault("components", {})
    component_schemas = components.setdefault("schemas", {})
    if "RuntimeApiProblem" not in component_schemas:
        component_schemas["RuntimeApiProblem"] = RuntimeApiProblem.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )

    for path, _, operation in _iter_operations(mutated):
        operation_id = operation.get("operationId")
        responses = operation.setdefault("responses", {})
        if not isinstance(responses, dict):
            continue

        for status_code, descriptor in _DEFAULT_PROBLEM_RESPONSES.items():
            response = responses.get(status_code)
            if not isinstance(response, dict):
                response = {"description": descriptor["description"]}
                responses[status_code] = response
            response.setdefault("description", descriptor["description"])
            content = response.setdefault("content", {})
            if not isinstance(content, dict):
                continue
            payload = content.setdefault("application/problem+json", {})
            if not isinstance(payload, dict):
                continue
            payload.setdefault("schema", {"$ref": "#/components/schemas/RuntimeApiProblem"})
            if "example" not in payload and not payload.get("examples"):
                payload["examples"] = {
                    "default": {
                        "summary": descriptor["description"],
                        "value": _problem_example(
                            status_code=int(status_code),
                            code=descriptor["code"],
                            path=path,
                        ),
                    }
                }

        success_response = responses.get("200")
        if not isinstance(success_response, dict):
            continue
        success_content = success_response.get("content")
        if not isinstance(success_content, dict):
            continue
        success_json = success_content.get("application/json")
        if not isinstance(success_json, dict):
            continue
        if "example" in success_json or success_json.get("examples"):
            continue
        if not isinstance(operation_id, str):
            continue
        example = _SUCCESS_EXAMPLES_BY_OPERATION.get(operation_id)
        if example is None:
            continue
        success_json["examples"] = {
            "default": {
                "summary": f"{operation_id} response example",
                "value": example,
            }
        }

    return mutated


def install_runtime_openapi_contract(app: Any) -> None:
    """Install runtime openapi contract helper."""
    original_openapi = app.openapi
    cached: dict[str, Any] | None = None

    def _custom_openapi() -> dict[str, Any]:
        nonlocal cached
        if cached is None:
            cached = augment_runtime_openapi(original_openapi())
        return cached

    app.openapi = _custom_openapi


def validate_runtime_openapi_contract(schema: dict[str, Any]) -> list[str]:
    """Validate runtime openapi contract."""
    violations: list[str] = []
    for path, method, operation in _iter_operations(schema):
        responses = operation.get("responses")
        if not isinstance(responses, dict):
            violations.append(f"{method.upper()} {path}: missing responses object")
            continue

        success = responses.get("200")
        success_example_found = False
        if isinstance(success, dict):
            content = success.get("content")
            if isinstance(content, dict):
                json_content = content.get("application/json")
                if isinstance(json_content, dict):
                    success_example_found = bool(
                        ("example" in json_content) or json_content.get("examples")
                    )
        if not success_example_found:
            violations.append(f"{method.upper()} {path}: missing success response example")

        for status_code in ("400", "401", "403", "404", "422", "500"):
            response = responses.get(status_code)
            if not isinstance(response, dict):
                violations.append(f"{method.upper()} {path}: missing {status_code} response")
                continue
            content = response.get("content")
            if not isinstance(content, dict):
                violations.append(
                    f"{method.upper()} {path}: {status_code} response missing content"
                )
                continue
            problem_payload = content.get("application/problem+json")
            if not isinstance(problem_payload, dict):
                violations.append(
                    (
                        f"{method.upper()} {path}: {status_code} response "
                        "missing application/problem+json"
                    )
                )
                continue
            if "schema" not in problem_payload:
                violations.append(
                    f"{method.upper()} {path}: {status_code} response missing problem schema"
                )
            if "example" not in problem_payload and not problem_payload.get("examples"):
                violations.append(
                    f"{method.upper()} {path}: {status_code} response missing problem example"
                )

    return violations


__all__ = [
    "augment_runtime_openapi",
    "install_runtime_openapi_contract",
    "validate_runtime_openapi_contract",
]
