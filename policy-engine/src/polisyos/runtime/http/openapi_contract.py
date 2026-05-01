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
_TEMPORAL_SCOPE_SAMPLE = {
    "valid_at": _TS_SAMPLE,
    "tx_at": "2026-02-11T12:01:00Z",
    "branch": "main",
    "snapshot_id": None,
    "scenario_id": None,
}
_TEMPORAL_RANGE_SAMPLE = {
    "earliest": "2026-02-11T11:59:00Z",
    "latest": "2026-02-11T12:01:00Z",
}
_TEMPORAL_EVENT_SAMPLE = {
    "id": f"{_RUN_ID_SAMPLE}:start",
    "timestamp": "2026-02-11T11:59:00Z",
    "kind": "run_start",
    "label": "Run started",
    "valid_at": "2026-02-11T11:59:00Z",
    "tx_at": "2026-02-11T11:59:00Z",
    "observed": True,
}
_TRUST_METADATA_SAMPLE = {
    "hash": "sha256:" + "b" * 64,
    "verification_status": "verified",
    "verified_by": "PolicyOSLineageVerifier@1.0",
    "verified_at": _TS_SAMPLE,
    "verification_method": "lineage_hash_match",
    "freshness": "current",
    "dispute_status": "none",
    "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
}
_LINEAGE_VIEW_SAMPLE = {
    "id": "artifact:" + _ARTIFACT_ID_SAMPLE,
    "status": "verified",
    "hash": "sha256:" + "b" * 64,
    "freshness": "current",
    "compact_summary": [
        {"kind": "source", "label": "fabric.data_snapshot", "id": _ARTIFACT_ID_SAMPLE},
        {"kind": "result", "label": "scientist.decision_packet", "id": _ARTIFACT_ID_SAMPLE},
    ],
    "nodes": [
        {
            "id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.decision_packet",
            "label": "scientist.decision_packet",
            "timestamp": None,
            "metadata": {"status": "present", "depth": 0},
        }
    ],
    "edges": [],
    "exports": {
        "openlineage": f"/api/v1/lineage/artifact:{_ARTIFACT_ID_SAMPLE}/export/openlineage",
        "prov": f"/api/v1/lineage/artifact:{_ARTIFACT_ID_SAMPLE}/export/prov",
    },
    "metadata": {"total_nodes": 1, "total_edges": 0},
    "trust_metadata": _TRUST_METADATA_SAMPLE,
}
_QUANTITY_VALUE_SAMPLE = {
    "point": 0.23,
    "unit": {"code": "1", "system": "ucum", "display": "ratio"},
    "metric_id": "employment_rate_delta",
    "lineage": _LINEAGE_VIEW_SAMPLE,
    "uncertainty": {
        "ci_95": [0.15, 0.31],
        "method": "bootstrap",
        "identifiability": "estimated",
        "disputed": False,
    },
    "time": _TEMPORAL_SCOPE_SAMPLE,
    "quantity_class": "decision",
    "label": "Employment rate",
}
_SCENARIO_ID_SAMPLE = "scn_rate_cut_25bps"
_SCENARIO_REF_SAMPLE = {
    "id": _SCENARIO_ID_SAMPLE,
    "status": "computed",
    "baseline_run_id": _RUN_ID_SAMPLE,
    "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
    "lineage": _LINEAGE_VIEW_SAMPLE,
    "assumption_ids": ["asm_no_external_shock"],
    "manifest_hash": "sha256:" + "c" * 64,
}
_SCENARIO_MANIFEST_SAMPLE = {
    "id": _SCENARIO_ID_SAMPLE,
    "baseline_run_id": _RUN_ID_SAMPLE,
    "status": "computed",
    "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
    "policy_question": "What if the policy rate is cut by 25 bps?",
    "author": "Fixture Analyst",
    "affected_population": "national_workforce",
    "temporal_window": _TEMPORAL_RANGE_SAMPLE,
    "model_family": "DoubleML",
    "model_version": "2.1",
    "model_lineage": _LINEAGE_VIEW_SAMPLE,
    "baseline_lineage": _LINEAGE_VIEW_SAMPLE,
    "baseline_hash": "sha256:" + "d" * 64,
    "computed_at": _TS_SAMPLE,
    "validity_window": _TEMPORAL_RANGE_SAMPLE,
    "known_limitations": ["Fixture scenario for contract documentation."],
    "stale_reasons": [],
    "interventions": [
        {
            "field": "policy_rate",
            "operator": "set",
            "value": _QUANTITY_VALUE_SAMPLE,
            "baseline_value": _QUANTITY_VALUE_SAMPLE,
            "constraint_ids": [],
        }
    ],
    "assumptions": [
        {
            "id": "asm_no_external_shock",
            "label": "No external demand shock",
            "status": "operator_assumption",
            "lineage": _LINEAGE_VIEW_SAMPLE,
            "description": "Fixture assumption for scenario reproducibility.",
        }
    ],
    "constraints": [],
}
_BUREAUCRATIC_DOCUMENT_SAMPLE = {
    "id": "doc_fixture_001",
    "packet_id": _ARTIFACT_ID_SAMPLE,
    "genre": "postanova_kmu",
    "jurisdiction": "ua",
    "template": {
        "id": "ua.kmu.postanova.v1",
        "version": "1.0.0",
        "genre": "postanova_kmu",
        "jurisdiction": "ua",
        "locale": "uk-UA",
        "legal_review_status": "pending_external_review",
    },
    "status": "draft",
    "title": "Draft policy artifact",
    "language": "uk",
    "watermark": "Generated by PolicyOS / Draft / Not an official state document",
    "render_timestamp": _TS_SAMPLE,
    "packet_hash": _ARTIFACT_ID_SAMPLE,
    "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
    "trust_view": True,
    "blocks": [],
    "annexes": [],
    "epistemic_summary": {
        "evidence_filled": 0.54,
        "model_generated": 0.22,
        "operator_filled": 0.18,
        "imported": 0.06,
    },
    "metadata": {"template_version": "ua.kmu.postanova.v1"},
}

_DEFAULT_PROBLEM_RESPONSES: dict[str, dict[str, str]] = {
    "400": {"code": "bad_request", "description": "Malformed request payload or parameters."},
    "401": {"code": "unauthorized", "description": "Authentication is required for this route."},
    "403": {
        "code": "forbidden",
        "description": "Authenticated principal cannot access this resource.",
    },
    "404": {"code": "not_found", "description": "Requested resource does not exist."},
    "406": {
        "code": "not_acceptable",
        "description": "Requested representation is not supported for this resource.",
    },
    "422": {"code": "request_validation_failed", "description": "Request validation failed."},
    "500": {"code": "internal_error", "description": "Unexpected runtime API failure."},
}

_SUCCESS_LINKS_BY_OPERATION: dict[str, dict[str, dict[str, Any]]] = {
    "get_artifact_manifest": {
        "artifactPreview": {
            "operationId": "get_artifact_content",
            "parameters": {"artifact_id": "$response.body#/artifact/artifact_id"},
            "description": "Fetch a preview or raw representation for the same artifact.",
        },
        "artifactDownload": {
            "operationId": "download_artifact_content",
            "parameters": {"artifact_id": "$response.body#/artifact/artifact_id"},
            "description": "Download the immutable binary payload for the same artifact.",
        },
        "artifactSchema": {
            "operationId": "get_artifact_schema",
            "parameters": {"artifact_id": "$response.body#/artifact/artifact_id"},
            "description": "Inspect the schema contract associated with the same artifact.",
        },
        "artifactLineage": {
            "operationId": "get_artifact_lineage",
            "parameters": {"artifact_id": "$response.body#/artifact/artifact_id"},
            "description": "Traverse lineage for the same artifact.",
        },
    },
    "get_run_details": {
        "runTimeline": {
            "operationId": "get_run_timeline",
            "parameters": {"run_id": "$response.body#/run/run_id"},
            "description": "Load the timeline for the same run.",
        },
        "runNodes": {
            "operationId": "get_run_nodes",
            "parameters": {"run_id": "$response.body#/run/run_id"},
            "description": "Load node-level execution details for the same run.",
        },
        "runLineage": {
            "operationId": "get_run_lineage",
            "parameters": {"run_id": "$response.body#/run/run_id"},
            "description": "Traverse lineage rooted at the same run.",
        },
        "runQuantities": {
            "operationId": "get_run_quantities",
            "parameters": {"run_id": "$response.body#/run/run_id"},
            "description": "Inspect QuantityValue coverage for the same run.",
        },
        "runFabricDecisionData": {
            "operationId": "get_run_fabric_decision_data",
            "parameters": {"run_id": "$response.body#/run/run_id"},
            "description": "Inspect Fabric trust envelopes for decision-bearing run values.",
        },
        "runAgents": {
            "operationId": "get_run_agents",
            "parameters": {"run_id": "$response.body#/run/run_id"},
            "description": "Inspect the agent/reflexion pipeline for the same run.",
        },
        "runEvidenceContext": {
            "operationId": "get_run_evidence_context",
            "parameters": {"run_id": "$response.body#/run/run_id"},
            "description": "Inspect the evidence context linked to the same run.",
        },
        "runWorkflow": {
            "operationId": "get_run_workflow",
            "parameters": {"run_id": "$response.body#/run/run_id"},
            "description": "Inspect the workflow graph for the same run.",
        },
    },
    "get_mobility_report": {
        "mobilityBounds": {
            "operationId": "get_mobility_report_bounds",
            "parameters": {"artifact_id": "$response.body#/mobility_report_ref/artifact_id"},
            "description": "Load the linked bounds bundle for the same mobility report.",
        },
        "mobilityDiagnostics": {
            "operationId": "get_mobility_report_diagnostics",
            "parameters": {"artifact_id": "$response.body#/mobility_report_ref/artifact_id"},
            "description": "Load diagnostics for the same mobility report.",
        },
    },
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
            "mode.analyst",
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
        "temporal_scope": None,
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
    "get_run_equilibria": {
        "meta": _META_CORE_RUN,
        "equilibria": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "report_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "report": {
                "schema_version": "1.0",
                "model_id": "ks_lite_v1",
                "search_protocol": {
                    "mode": "baseline",
                    "start_domain": {"belief_slope": [0.0, 1.0]},
                    "n_attempts": 16,
                    "continuation_grid": [],
                    "merge_tol": 1.0e-6,
                    "residual_tol": 1.0e-8,
                    "basin_draws": 64,
                },
                "equilibria": [
                    {
                        "equilibrium_id": "eq_001",
                        "state": {
                            "variable_ids": ["belief_slope"],
                            "values": [0.72],
                            "scales": [1.0],
                            "lower_bounds": [0.0],
                            "upper_bounds": [1.0],
                            "weights": [1.0],
                            "notes": [],
                        },
                        "residual_norm": 1.0e-9,
                        "local_stability": "attractive",
                        "discovered_from_starts": 8,
                        "notes": [],
                    }
                ],
                "branches": [
                    {
                        "branch_id": "br_001",
                        "points": [{"lambda": 0.0, "equilibrium_id": "eq_001"}],
                        "notes": ["single_parameter_point"],
                    }
                ],
                "bifurcation_candidates": [],
                "basin_estimates": [],
                "unresolved_starts": [],
                "global_diagnostics": {
                    "num_attempts": 16,
                    "num_converged": 16,
                    "num_equilibria": 1,
                    "num_unresolved": 0,
                    "two_cycle_failures": 0,
                    "stagnation_failures": 0,
                    "divergence_failures": 0,
                },
                "provenance": {
                    "solver_version": "polisyos-foundry-feedback-1.0",
                    "git_sha": "fixture",
                    "runtime_refs": [],
                },
                "notes": [],
            },
            "notes": [],
        },
    },
    "get_runs_batch": {
        "meta": _META_CORE_RUN,
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
            }
        ],
    },
    "get_temporal_capabilities": {
        "meta": _META_CORE_RUN,
        "capabilities": {
            "run_id": _RUN_ID_SAMPLE,
            "default_scope": _TEMPORAL_SCOPE_SAMPLE,
            "valid_range": _TEMPORAL_RANGE_SAMPLE,
            "tx_range": _TEMPORAL_RANGE_SAMPLE,
            "resolution": "event",
            "event_points": [_TEMPORAL_EVENT_SAMPLE],
            "surfaces": [
                {
                    "surface": "run_details",
                    "supported": True,
                    "resolution": "event",
                    "reason_code": None,
                    "valid_range": _TEMPORAL_RANGE_SAMPLE,
                    "tx_range": _TEMPORAL_RANGE_SAMPLE,
                    "nearest_event_points": [_TEMPORAL_EVENT_SAMPLE],
                    "gaps": [],
                },
                {
                    "surface": "run_agents",
                    "supported": False,
                    "resolution": "unsupported",
                    "reason_code": "temporal_surface_unsupported",
                    "valid_range": _TEMPORAL_RANGE_SAMPLE,
                    "tx_range": _TEMPORAL_RANGE_SAMPLE,
                    "nearest_event_points": [_TEMPORAL_EVENT_SAMPLE],
                    "gaps": [],
                },
            ],
        },
    },
    "estimate_mobility": {
        "meta": _META_NO_SOURCE,
        "report": {
            "schema_version": "2.0",
            "artifact_name": "mobility_report_v2.json",
            "analysis_type": "transition_matrix_attrition_adjusted",
            "estimand_id": "mobility.transition_matrix.attrition_adjusted",
            "status": "ok",
            "population": {
                "target_population": "panel baseline cohort",
                "weights_design": "uniform",
                "panel_length": 2,
                "waves_used": [1, 2],
                "class_definition": {"type": "preclassified", "n_classes": 2},
            },
            "attrition": {
                "pattern": "panel_attrition",
                "monotone": True,
                "mechanism_assumed": "mar_given_observables",
                "refreshment_sample": False,
                "positivity_floor": 0.05,
                "weight_model": {
                    "family": "provided_probabilities",
                    "features": [],
                    "metadata": {},
                },
                "outcome_model": {
                    "family": "weighted_linear_probability",
                    "features": ["x_0"],
                    "metadata": {},
                },
            },
            "point_estimate": {
                "joint_matrix": [[0.25, 0.25], [0.25, 0.25]],
                "transition_matrix": [[0.5, 0.5], [0.5, 0.5]],
                "row_marginals": [0.5, 0.5],
                "col_marginals": [0.5, 0.5],
                "mobility_stats": {
                    "upward_rate": 0.25,
                    "downward_rate": 0.25,
                    "immobility_rate": 0.5,
                    "shorrocks_index": 0.5,
                },
            },
            "uncertainty": {
                "method": "aipw_point_only",
                "standard_errors": {},
                "confidence_intervals": {},
                "bootstrap": {},
                "covariance_ref": None,
            },
            "bounds": {
                "bundle_ref": {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "kind": "ir.bounds_bundle",
                    "media_type": "application/json",
                },
                "cell_bounds": {"0,0": [0.2, 0.4]},
                "summary_bounds": {"upward_rate": [0.1, 0.4]},
                "sharpness_status": "sharp_with_row_marginals",
                "method": "sharp_transport_bounds_row_marginals",
            },
            "diagnostics": {
                "effective_sample_size": 120.5,
                "max_weight": 2.8,
                "p99_weight": 2.3,
                "min_retention_probability": 0.3,
                "max_retention_probability": 0.9,
                "observed_retention_rate": 0.6,
                "observed_full_cases": 120,
                "balance": {"max_abs_smd_before": 0.4, "max_abs_smd_after": 0.08},
                "placebo_checks": {},
                "sensitivity_grid": {},
                "warnings": [],
            },
            "assumptions": [
                "class_definition_fixed_ex_ante",
                "mar_given_observables",
                "positivity",
                "origin_class_observed_for_all_units",
            ],
            "summary_metrics": {
                "transition_matrix": [[0.5, 0.5], [0.5, 0.5]],
                "upward_mobility_rate": 0.25,
                "downward_mobility_rate": 0.25,
                "immobility_rate": 0.5,
                "n_classes": 2,
                "n_obs": 120,
            },
            "sensitivity_envelope": {
                "summary_bounds": {"upward_rate": [0.1, 0.4]},
                "bounds_method": "sharp_transport_bounds_row_marginals",
            },
            "upstream_refs": [f"artifact://{_ARTIFACT_ID_SAMPLE}"],
            "metadata": {"estimator": "aipw"},
        },
        "mobility_report_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "ir.mobility_report",
            "media_type": "application/json",
        },
        "bounds_bundle_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "ir.bounds_bundle",
            "media_type": "application/json",
        },
    },
    "compute_mobility_bounds": {
        "meta": _META_NO_SOURCE,
        "bounds": {
            "schema_version": "1.0",
            "estimand_type": "mobility.upward_rate",
            "point_identified": False,
            "lower_bound": 0.1,
            "upper_bound": 0.4,
            "consensus_lower": 0.1,
            "consensus_upper": 0.4,
            "dual_certificate_ref": None,
            "sharpness_status": "unknown",
            "tightening_status": "not_run",
            "tightening_stop_reason": None,
            "tightening_log_ref": None,
            "best_in_class_claim": None,
            "method_summaries": [
                {
                    "method": "transport_bounds",
                    "lower_bound": 0.1,
                    "upper_bound": 0.4,
                    "bound_width": 0.3,
                    "certificate_ref": None,
                    "assumptions_used": [
                        "observed_stayers_are_lower_bounds",
                        "known_row_marginals",
                    ],
                    "bounds_type": "sharp_lp",
                    "display_label": "sharp_transport_bounds_row_marginals",
                    "certificate_kind": None,
                    "soundness_level": None,
                    "solver_metadata": {
                        "headline_metric": "upward_rate",
                        "n_rows": 2,
                        "n_cols": 2,
                        "column_marginals_supplied": False,
                    },
                }
            ],
            "rescue_actions": [],
            "warnings": ["destination_marginals_missing_bounds_may_be_wide"],
            "metadata": {
                "headline_metric": "upward_rate",
                "bounds_method": "sharp_transport_bounds_row_marginals",
                "summary_bounds": {"upward_rate": [0.1, 0.4]},
            },
        },
        "bounds_bundle_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "ir.bounds_bundle",
            "media_type": "application/json",
        },
        "mobility_report_ref": None,
        "cell_bounds": {"0,0": [0.2, 0.4], "0,1": [0.1, 0.3]},
        "summary_bounds": {"upward_rate": [0.1, 0.4], "immobility_rate": [0.4, 0.9]},
    },
    "estimate_causal_frontier_sae": {
        "meta": _META_NO_SOURCE,
        "method_name": "survey.sae.causal_frontier_fay_herriot",
        "estimates": [
            {
                "area_id": "area_001",
                "theta_mean": 0.18,
                "theta_sd": 0.04,
                "mse": 0.0016,
                "component_id": 0,
                "borrow_strength_neighbors": 3,
            }
        ],
        "diagnostics": {
            "n_areas": 1,
            "green_share": 1.0,
            "max_frontier_gap": 0.03,
        },
        "governance_artifact": {
            "status": "pass",
            "issues": [],
            "summary": {"green": 1, "amber": 0, "red": 0},
        },
        "artifact_refs": {
            "dependence_ref": {
                "artifact_id": _ARTIFACT_ID_SAMPLE,
                "kind": "spatial.dependence_bundle",
                "media_type": "application/json",
            },
            "quality_certificate_ref": {
                "artifact_id": _ARTIFACT_ID_SAMPLE,
                "kind": "fabric.quality_report",
                "media_type": "application/json",
            },
            "sae_estimates_ref": {
                "artifact_id": _ARTIFACT_ID_SAMPLE,
                "kind": "survey.sae_estimates_bundle",
                "media_type": "application/json",
            },
            "causal_diagnostics_ref": {
                "artifact_id": _ARTIFACT_ID_SAMPLE,
                "kind": "survey.causal_frontier_diagnostics",
                "media_type": "application/json",
            },
            "governance_artifact_ref": {
                "artifact_id": _ARTIFACT_ID_SAMPLE,
                "kind": "scientist.governance_report",
                "media_type": "application/json",
            },
        },
        "output_bundle": {
            "output_dir": "artifacts/causal_frontier_sae",
            "diagnostics_path": "artifacts/causal_frontier_sae/diagnostics.json",
        },
    },
    "get_mobility_report": {
        "meta": _META_NO_SOURCE,
        "report": {
            "schema_version": "2.0",
            "artifact_name": "mobility_report_v2.json",
            "analysis_type": "transition_matrix_attrition_adjusted",
            "status": "ok",
            "summary_metrics": {"n_classes": 2, "n_obs": 120},
            "sensitivity_envelope": {"summary_bounds": {"upward_rate": [0.1, 0.4]}},
            "upstream_refs": [f"artifact://{_ARTIFACT_ID_SAMPLE}"],
            "metadata": {"estimator": "aipw"},
        },
        "mobility_report_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "ir.mobility_report",
            "media_type": "application/json",
        },
    },
    "get_mobility_report_bounds": {
        "meta": _META_NO_SOURCE,
        "bounds": {
            "schema_version": "1.0",
            "estimand_type": "mobility.upward_rate",
            "point_identified": False,
            "lower_bound": 0.1,
            "upper_bound": 0.4,
            "consensus_lower": 0.1,
            "consensus_upper": 0.4,
            "dual_certificate_ref": None,
            "sharpness_status": "unknown",
            "tightening_status": "not_run",
            "tightening_stop_reason": None,
            "tightening_log_ref": None,
            "best_in_class_claim": None,
            "method_summaries": [],
            "rescue_actions": [],
            "warnings": [],
            "metadata": {"headline_metric": "upward_rate"},
        },
        "bounds_bundle_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "ir.bounds_bundle",
            "media_type": "application/json",
        },
        "mobility_report_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "ir.mobility_report",
            "media_type": "application/json",
        },
        "cell_bounds": {"0,0": [0.2, 0.4]},
        "summary_bounds": {"upward_rate": [0.1, 0.4]},
    },
    "get_mobility_report_diagnostics": {
        "meta": _META_NO_SOURCE,
        "diagnostics": {
            "effective_sample_size": 120.5,
            "max_weight": 2.8,
            "p99_weight": 2.3,
            "min_retention_probability": 0.3,
            "max_retention_probability": 0.9,
            "observed_retention_rate": 0.6,
            "observed_full_cases": 120,
            "balance": {"max_abs_smd_before": 0.4, "max_abs_smd_after": 0.08},
            "placebo_checks": {},
            "sensitivity_grid": {},
            "warnings": [],
        },
        "mobility_report_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "ir.mobility_report",
            "media_type": "application/json",
        },
    },
    "analyze_attractors": {
        "schema_version": "1.0",
        "ok": True,
        "analysis_result": {
            "schema_version": "1.0",
            "kind": "foundry.attractor_analysis_result",
            "analysis_id": "sha256:" + "d" * 64,
            "model_ref": None,
            "simulation_result_ref": None,
            "exec_plan_ref": None,
            "feedback_result_ref": None,
            "state_projection": {
                "variables": ["infected", "susceptible"],
                "reduced_dimension": 2,
                "quotient_notes": ["time_step excluded"],
            },
            "parameter_point": {"names": ["beta", "gamma"], "values": [0.35, 0.1]},
            "attractors": [
                {
                    "attractor_id": "A1",
                    "kind": "fixed_point",
                    "existence_status": "numerically_confirmed",
                    "state_representation": {
                        "equilibrium": {"infected": 0.0, "susceptible": 127.3},
                        "section_definition": None,
                        "orbit_artifact_ref": None,
                        "orbit_points": [],
                        "invariant_set_artifact_ref": None,
                        "summary": {},
                    },
                    "stability": {
                        "local_class": "asymptotically_stable",
                        "jacobian_eigenvalues": [],
                        "spectral_radius": 0.84,
                        "floquet_multipliers": None,
                        "lyapunov_spectrum": None,
                        "largest_lyapunov_exponent": None,
                        "diagnostics": {},
                        "notes": [],
                    },
                    "certificate": {
                        "type": "trajectory_diagnostic",
                        "status": "numerically_supported",
                        "evidence_strength": 0.7,
                        "V_description": None,
                        "proof_artifact_ref": None,
                        "notes": ["finite_time_numerical_evidence"],
                    },
                    "basin": {
                        "estimation_method": "multi_start_ensemble",
                        "basin_measure_estimate": 0.72,
                        "confidence_interval": [0.68, 0.76],
                        "boundary_complexity": "simple",
                        "basin_map_ref": None,
                        "notes": [],
                    },
                    "observables": {
                        "period": None,
                        "max_amplitude": 0.0,
                        "terminal_residual_norm": 1.0e-8,
                        "summary": {},
                    },
                    "uncertainty": {
                        "seeds_used": 64,
                        "numerical_tolerance": 1.0e-7,
                        "continuation_step": None,
                        "finite_time_horizon": 240,
                        "notes": [],
                    },
                    "notes": [],
                }
            ],
            "bifurcations": [],
            "uncertainty_summary": {
                "stochastic_model": True,
                "seed_ensemble_size": 64,
                "unresolved_items": [],
                "notes": [],
            },
            "provenance": {
                "toolchain": ["polisyos.foundry.analysis.attractors"],
                "derived_from": [],
                "notes": [],
            },
            "notes": ["basin_map_available"],
        },
        "analysis_result_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "foundry.attractor_analysis_result",
            "media_type": "application/json",
        },
        "derived_refs": [
            {
                "role": "attractor_analysis_result",
                "ref": {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "kind": "foundry.attractor_analysis_result",
                    "media_type": "application/json",
                },
            }
        ],
        "notes": ["basin_map_available"],
    },
    "analyze_lyapunov_diagnostics": {
        "schema_version": "1.0",
        "ok": True,
        "analysis_result": {
            "schema_version": "1.0",
            "kind": "foundry.attractor_analysis_result",
            "analysis_id": "sha256:" + "e" * 64,
            "state_projection": {
                "variables": ["x"],
                "reduced_dimension": 1,
                "quotient_notes": ["reduced_observable_state"],
            },
            "parameter_point": {"names": ["r"], "values": [4.0]},
            "attractors": [
                {
                    "attractor_id": "A1",
                    "kind": "chaotic",
                    "existence_status": "numerically_confirmed",
                    "state_representation": {"summary": {"terminal_mean": {"x": 0.5}}},
                    "stability": {
                        "local_class": "mixed",
                        "largest_lyapunov_exponent": 0.69,
                    },
                    "certificate": {
                        "type": "trajectory_diagnostic",
                        "status": "numerically_supported",
                        "evidence_strength": 0.55,
                    },
                    "basin": {"estimation_method": "single_trajectory"},
                    "observables": {"terminal_residual_norm": 0.12},
                    "uncertainty": {"numerical_tolerance": 1.0e-6},
                    "notes": ["positive_largest_lyapunov_exponent"],
                }
            ],
            "bifurcations": [],
            "uncertainty_summary": {
                "stochastic_model": False,
                "seed_ensemble_size": None,
                "unresolved_items": [],
                "notes": [],
            },
            "provenance": {
                "toolchain": ["polisyos.foundry.analysis.attractors"],
                "derived_from": [],
                "notes": [],
            },
            "notes": [],
        },
        "analysis_result_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "foundry.attractor_analysis_result",
            "media_type": "application/json",
        },
        "derived_refs": [],
        "notes": [],
    },
    "persist_basin_map": {
        "artifact_id": _ARTIFACT_ID_SAMPLE,
        "kind": "foundry.basin_map",
        "media_type": "application/json",
    },
    "persist_continuation_branch": {
        "artifact_id": _ARTIFACT_ID_SAMPLE,
        "kind": "foundry.continuation_branch",
        "media_type": "application/json",
    },
    "get_attractor_analysis": {
        "schema_version": "1.0",
        "kind": "foundry.attractor_analysis_result",
        "analysis_id": "sha256:" + "d" * 64,
        "state_projection": {
            "variables": ["infected"],
            "reduced_dimension": 1,
            "quotient_notes": ["time_step excluded"],
        },
        "parameter_point": {"names": ["beta"], "values": [0.35]},
        "attractors": [],
        "bifurcations": [],
        "uncertainty_summary": {
            "stochastic_model": False,
            "seed_ensemble_size": None,
            "unresolved_items": [],
            "notes": [],
        },
        "provenance": {"toolchain": [], "derived_from": [], "notes": []},
        "notes": [],
    },
    "get_analysis_basin_map": {
        "schema_version": "1.0",
        "kind": "foundry.basin_map",
        "basin_id": "sha256:" + "f" * 64,
        "analysis_id": "sha256:" + "d" * 64,
        "state_projection": {
            "variables": ["x"],
            "reduced_dimension": 1,
            "quotient_notes": ["multi_start_ensemble"],
        },
        "sampling_method": "multi_start_ensemble",
        "samples": [
            {
                "sample_id": "S1",
                "initial_state": {"x": 0.1},
                "attractor_id": "A1",
                "seed": 1,
                "terminal_residual_norm": 1.0e-8,
                "confidence": 1.0,
                "notes": [],
            }
        ],
        "basin_measure_estimates": {"A1": 1.0},
        "notes": [],
    },
    "get_analysis_continuation_branch": {
        "schema_version": "1.0",
        "kind": "foundry.continuation_branch",
        "branch_id": "branch_1",
        "analysis_id": "sha256:" + "d" * 64,
        "branch_kind": "equilibrium",
        "parameters": ["beta"],
        "points": [
            {
                "point_id": "p1",
                "parameter_values": {"beta": 0.35},
                "state": {"infected": 0.0},
                "period": None,
                "stability": {"local_class": "asymptotically_stable"},
                "bifurcation_id": None,
                "notes": [],
            }
        ],
        "bifurcations": [],
        "toolchain": ["continuation_reference_solver"],
        "notes": [],
    },
    "get_run_timeline": {
        "meta": _META_CORE_RUN,
        "temporal_scope": None,
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
        "temporal_scope": None,
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
    "get_run_quantities": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "source_kind": "core_run",
        "temporal_scope": None,
        "quantities": [
            {
                "point": 100.0,
                "unit": {"code": "[USD]", "system": "ucum", "display": "USD"},
                "metric_id": "policy_cost",
                "lineage": {
                    "id": "artifact:" + _ARTIFACT_ID_SAMPLE,
                    "hash": None,
                    "status": "verified",
                    "freshness": "current",
                    "summary": {
                        "source": "decision_packet.simulation_results.policy_cost",
                        "artifact": _ARTIFACT_ID_SAMPLE,
                    },
                    "compact_summary": [
                        {
                            "kind": "source",
                            "label": "Decision packet",
                            "id": _ARTIFACT_ID_SAMPLE,
                        },
                        {
                            "kind": "result",
                            "label": "decision_packet.simulation_results.policy_cost",
                            "id": "artifact:" + _ARTIFACT_ID_SAMPLE,
                        },
                    ],
                    "reason_code": None,
                    "tracking_issue": None,
                },
                "uncertainty": None,
                "time": {"valid_at": _TS_SAMPLE, "tx_at": _TS_SAMPLE},
                "quantity_class": "decision",
                "label": "policy_cost",
            }
        ],
        "coverage": {
            "total": 1,
            "decision": 1,
            "telemetry": 0,
            "layout": 0,
            "debug": 0,
            "traced": 1,
            "untraced": 0,
        },
        "entries": [
            {
                "path": "decision_packet.simulation_results.policy_cost",
                "quantity_class": "decision",
                "status": "verified",
                "lineage_id": "artifact:" + _ARTIFACT_ID_SAMPLE,
                "metric_id": "policy_cost",
                "reason_code": None,
                "tracking_issue": None,
            }
        ],
    },
    "get_run_fabric_decision_data": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "source_kind": "core_run",
        "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
        "decision_data": [
            {
                "id": "fabric_decision_data:policy_cost",
                "kind": "quantity",
                "value": {
                    "point": 100.0,
                    "unit": {"code": "[USD]", "system": "ucum", "display": "USD"},
                    "semantic_type": "policy_cost",
                    "metric_id": "policy_cost",
                    "label": "policy_cost",
                },
                "source_contract": {
                    "id": "worldbank.wdi.generic",
                    "version": "1.1.0",
                },
                "quality": {
                    "status": "passed",
                    "score": 1.0,
                    "report_ref": "runtime://quantity-quality/policy_cost",
                    "reason_code": None,
                    "quality_surface": None,
                    "remediation_link": None,
                },
                "lineage": {
                    "id": "artifact:" + _ARTIFACT_ID_SAMPLE,
                    "status": "verified",
                    "hash": None,
                    "compact_summary_ref": "/api/v1/lineage/artifact:" + _ARTIFACT_ID_SAMPLE,
                    "full_graph_ref": "/api/v1/lineage/artifact:"
                    + _ARTIFACT_ID_SAMPLE
                    + "?view=full",
                    "raw_evidence_refs": ["cas://" + _ARTIFACT_ID_SAMPLE],
                    "export_links": {
                        "openlineage": "/api/v1/lineage/artifact:"
                        + _ARTIFACT_ID_SAMPLE
                        + "/export/openlineage",
                        "prov": "/api/v1/lineage/artifact:"
                        + _ARTIFACT_ID_SAMPLE
                        + "/export/prov",
                    },
                    "reason_code": None,
                    "owner": None,
                    "tracking_issue": None,
                },
                "access": {
                    "classification": "public",
                    "pii_tier": "none",
                    "tenant_scope": "shared_public",
                    "redaction": "none",
                    "policy_ref": None,
                },
                "time": _TEMPORAL_SCOPE_SAMPLE,
                "replay": {
                    "status": "replayable",
                    "manifest_ref": "cas://" + _ARTIFACT_ID_SAMPLE,
                    "reason_code": None,
                    "source_reason": None,
                    "retention_alternative": None,
                },
                "gaps": [],
                "metadata": {
                    "quantity_class": "decision",
                    "runtime_metric_id": "policy_cost",
                },
            }
        ],
        "coverage": {
            "total": 1,
            "decision": 1,
            "telemetry": 0,
            "layout": 0,
            "debug": 0,
            "traced": 1,
            "untraced": 0,
            "naked_decision_values": 0,
            "transitional_waivers": 0,
        },
    },
    "get_fabric_source_scorecards": {
        "meta": _META_NO_SOURCE,
        "schema_version": "fabric.source_scorecard.v1",
        "generated_at": _TS_SAMPLE,
        "count": 1,
        "scorecards": {
            "worldbank.wdi.generic": {
                "schema_version": "fabric.source_scorecard.v1",
                "source_contract_id": "worldbank.wdi.generic",
                "connector_id": "worldbank.wdi",
                "profile_id": "worldbank.default",
                "generated_at": _TS_SAMPLE,
                "window": "rolling_30d",
                "metrics": [
                    {
                        "name": "quality",
                        "score": 0.97,
                        "observed_value": 0.97,
                        "target_value": 0.8,
                        "status": "healthy",
                        "reason": "",
                    }
                ],
                "overall_score": 0.93,
                "grade": "A",
                "status": "healthy",
                "evidence": {"source_contract_hash": "sha256:" + "c" * 64},
            }
        },
    },
    "get_fabric_quality_batch": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
        "quality_refs": {
            "fabric_decision_data:policy_cost": {
                "status": "passed",
                "score": 1.0,
                "report_ref": "runtime://quantity-quality/policy_cost",
                "reason_code": None,
                "quality_surface": None,
                "remediation_link": None,
            }
        },
        "coverage": {
            "total": 1,
            "decision": 1,
            "traced": 1,
            "untraced": 0,
            "naked_decision_values": 0,
        },
    },
    "get_fabric_trust_batch": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
        "trust_refs": {
            "fabric_decision_data:policy_cost": {
                "quality": {"status": "passed", "score": 1.0},
                "access": {
                    "classification": "public",
                    "pii_tier": "none",
                    "tenant_scope": "shared_public",
                    "redaction": "none",
                    "policy_ref": None,
                },
                "lineage": {
                    "id": "artifact:" + _ARTIFACT_ID_SAMPLE,
                    "status": "verified",
                    "raw_evidence_refs": ["cas://" + _ARTIFACT_ID_SAMPLE],
                },
                "replay": {
                    "status": "replayable",
                    "manifest_ref": "cas://" + _ARTIFACT_ID_SAMPLE,
                },
                "time": _TEMPORAL_SCOPE_SAMPLE,
                "gaps": [],
            }
        },
        "coverage": {
            "total": 1,
            "decision": 1,
            "traced": 1,
            "untraced": 0,
            "naked_decision_values": 0,
        },
    },
    "get_fabric_run_replay": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
        "replay_refs": {
            "fabric_decision_data:policy_cost": {
                "status": "replayable",
                "manifest_ref": "cas://" + _ARTIFACT_ID_SAMPLE,
                "reason_code": None,
                "source_reason": None,
                "retention_alternative": None,
            }
        },
        "status_counts": {"replayable": 1},
        "coverage": {"decision": 1, "traced": 1, "untraced": 0},
    },
    "analyze_fabric_impact": {
        "meta": _META_CORE_RUN,
        "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
        "impacts": [
            {
                "subject_id": "artifact:" + _ARTIFACT_ID_SAMPLE,
                "subject_kind": "lineage",
                "lineage_status": "verified",
                "quality_status": "passed",
                "replay_status": "replayable",
                "downstream_refs": [],
                "upstream_refs": [],
                "affected_decision_data_ids": ["fabric_decision_data:policy_cost"],
                "source_contract_ids": ["worldbank.wdi.generic"],
                "evidence_refs": ["cas://" + _ARTIFACT_ID_SAMPLE],
                "notes": ["lineage graph loaded lazily through /api/v1/lineage/{lineage_id}"],
            }
        ],
        "summary": {
            "run_id": _RUN_ID_SAMPLE,
            "lineage_count": 1,
            "source_contract_count": 0,
            "decision_data_count": 1,
            "impact_count": 1,
        },
    },
    "get_lineage": {"meta": _META_NO_SOURCE, "lineage": _LINEAGE_VIEW_SAMPLE},
    "get_lineage_batch": {
        "meta": _META_NO_SOURCE,
        "lineages": [_LINEAGE_VIEW_SAMPLE],
    },
    "export_lineage_openlineage": {
        "meta": _META_NO_SOURCE,
        "lineage_id": "artifact:" + _ARTIFACT_ID_SAMPLE,
        "format": "openlineage",
        "payload": {
            "eventType": "COMPLETE",
            "producer": "polisyos-runtime-api",
            "run": {"runId": "artifact:" + _ARTIFACT_ID_SAMPLE},
            "job": {
                "namespace": "polisyos.runtime.lineage",
                "name": "artifact:" + _ARTIFACT_ID_SAMPLE,
            },
            "inputs": [],
            "outputs": [
                {"namespace": "polisyos.lineage", "name": "artifact:" + _ARTIFACT_ID_SAMPLE}
            ],
            "facets": {},
        },
    },
    "export_lineage_prov": {
        "meta": _META_NO_SOURCE,
        "lineage_id": "artifact:" + _ARTIFACT_ID_SAMPLE,
        "format": "prov",
        "payload": {
            "prefix": {"polisyos": "https://polisyos.dev/prov/"},
            "entity": {_ARTIFACT_ID_SAMPLE: {"prov:label": "scientist.decision_packet"}},
            "wasDerivedFrom": [],
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
                            "token_usage": {
                                "prompt_tokens": 411,
                                "completion_tokens": 92,
                                "total_tokens": 503,
                            },
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
    "compare_runs": {
        "meta": _META_CORE_RUN,
        "status": "computed",
        "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
        "comparison_frame": {
            "run_a": "R_core_api_001",
            "run_b": "R_core_api_002",
            "metric_set": ["employment_rate_delta"],
            "population": "national_workforce",
            "unit_policy": "canonical",
            "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
            "scenario_scope": {},
            "assumption_set": [],
        },
        "comparability": {
            "status": "compatible",
            "warnings": [],
            "blocked_reasons": [],
        },
        "deltas": [
            {
                "metric_id": "employment_rate_delta",
                "label": "Employment rate",
                "a": _QUANTITY_VALUE_SAMPLE,
                "b": _QUANTITY_VALUE_SAMPLE,
                "delta_absolute": _QUANTITY_VALUE_SAMPLE,
                "delta_relative": _QUANTITY_VALUE_SAMPLE,
                "delta_distribution": {
                    "quantiles": {"p50": 0.02, "p90": 0.05},
                    "mean_shift": 0.02,
                    "median_shift": 0.02,
                    "ci_overlap": True,
                },
                "significance": "uncertain",
                "dominance": "unknown",
                "decision_salience": 0.82,
                "lineage_delta": {
                    "source_changed": False,
                    "model_changed": False,
                    "hash_changed": False,
                    "freshness_changed": False,
                    "verification_changed": None,
                    "notes": [],
                },
            }
        ],
    },
    "get_run_compare_candidates": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "candidates": [
            {
                "run_id": "R_core_api_002",
                "label": "Previous governed run",
                "relation": "previous",
                "status": "completed",
                "started_at": _TS_SAMPLE,
                "finished_at": _TS_SAMPLE,
                "comparability": {
                    "status": "compatible",
                    "warnings": [],
                    "blocked_reasons": [],
                },
            }
        ],
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
    "get_artifact_batch": {
        "meta": _META_NO_SOURCE,
        "artifacts": [
            {
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
            }
        ],
    },
    "get_artifact_content": {
        "meta": _META_NO_SOURCE,
        "artifact": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.decision_packet",
            "media_type": "application/json",
            "mode": "json",
            "size_bytes": 1024,
            "max_bytes": 4096,
            "truncated": False,
            "preview": {
                "policy_answer": "Approve the targeted SME bridge support package.",
                "document_outline": [
                    {
                        "section_id": "policy_answer",
                        "section_type": "policy",
                        "title": "Recommendation",
                    }
                ],
                "metric_significance_by_metric": {
                    "gdp_change": {
                        "effect_size": 0.23,
                        "p_value": 0.02,
                        "test_label": "Paired t test",
                    }
                },
            },
            "decision_packet_preview": {
                "document_outline": [
                    {
                        "section_id": "policy_answer",
                        "section_type": "policy",
                        "title": "Recommendation",
                    }
                ],
                "metric_significance_by_metric": {
                    "gdp_change": {
                        "effect_size": {
                            "point": 0.23,
                            "ci_95": [0.12, 0.34],
                            "method": "analytic",
                        },
                        "p_value": 0.02,
                        "test_label": "Paired t test",
                    }
                },
            },
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
        "message": (
            "Natural-language run R_nl_abcdef02 accepted. "
            "Agent circuit was queued in mock mode: mock agents."
        ),
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
        "security_posture": {
            "required": False,
            "middleware_required": False,
            "authz_shadow_allowed": True,
        },
        "fallback_rules": {
            "mock_fallback_allowed": True,
            "policy_flag_required_for_mock_fallback": False,
        },
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
                "description": (
                    "Use the agent circuit to transform NL requests into executable policy runs."
                ),
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
    "list_run_scenarios": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
        "scenarios": [_SCENARIO_MANIFEST_SAMPLE],
    },
    "create_run_scenario": {
        "meta": _META_CORE_RUN,
        "scenario": _SCENARIO_MANIFEST_SAMPLE,
    },
    "get_run_counterfactual_metrics": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
        "scenario": _SCENARIO_MANIFEST_SAMPLE,
        "metrics": {
            "employment_rate_delta": {
                "metric_id": "employment_rate_delta",
                "label": "Employment rate",
                "actual": _QUANTITY_VALUE_SAMPLE,
                "counterfactual": _QUANTITY_VALUE_SAMPLE,
                "delta": _QUANTITY_VALUE_SAMPLE,
                "scenario_ref": _SCENARIO_REF_SAMPLE,
                "assumption_ids": ["asm_no_external_shock"],
            }
        },
    },
    "get_scenario_manifest": {
        "meta": _META_CORE_RUN,
        "scenario": _SCENARIO_MANIFEST_SAMPLE,
    },
    "get_scenario_capabilities": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "scenario_id": _SCENARIO_ID_SAMPLE,
        "temporal_scope": _TEMPORAL_SCOPE_SAMPLE,
        "capabilities": [
            {
                "surface": "run_metrics",
                "supported": True,
                "reason_code": None,
                "metric_id": "employment_rate_delta",
                "supported_modes": ["actual", "actual_vs_scenario", "scenario_only"],
                "limitations": [],
            }
        ],
    },
    "render_bureaucratic_artifact": {
        "meta": _META_NO_SOURCE,
        "document": _BUREAUCRATIC_DOCUMENT_SAMPLE,
    },
    "export_bureaucratic_artifact": {
        "meta": _META_NO_SOURCE,
        "document_id": "doc_fixture_001",
        "packet_id": _ARTIFACT_ID_SAMPLE,
        "format": "html",
        "content_type": "text/html; charset=utf-8",
        "filename": "doc_fixture_001.html",
        "content": "<article data-policyos-document=\"doc_fixture_001\"></article>",
        "metadata": {
            "watermark": _BUREAUCRATIC_DOCUMENT_SAMPLE["watermark"],
            "template_version": "ua.kmu.postanova.v1",
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


def _iter_operations(schema: dict[str, Any]) -> Any:
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
                response_payload: dict[str, Any] = {"description": descriptor["description"]}
                responses[status_code] = response_payload
            else:
                response_payload = response
            response_payload.setdefault("description", descriptor["description"])
            if "content" not in response_payload:
                response_payload["content"] = {}
            content = response_payload.get("content")
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
            pass
        elif isinstance(operation_id, str):
            example = _SUCCESS_EXAMPLES_BY_OPERATION.get(operation_id)
            if example is not None:
                success_json["examples"] = {
                    "default": {
                        "summary": f"{operation_id} response example",
                        "value": example,
                    }
                }
        if isinstance(operation_id, str):
            links = _SUCCESS_LINKS_BY_OPERATION.get(operation_id)
            if links and "links" not in success_response:
                success_response["links"] = deepcopy(links)

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
                        schema_obj = json_content.get("schema")
                        if isinstance(schema_obj, dict) and not schema_obj and len(content) > 1:
                            success_example_found = True
                elif content:
                    success_example_found = True
        if not success_example_found:
            violations.append(f"{method.upper()} {path}: missing success response example")
        operation_id = operation.get("operationId")
        if isinstance(operation_id, str):
            required_links = _SUCCESS_LINKS_BY_OPERATION.get(operation_id, {})
            if required_links:
                links = success.get("links") if isinstance(success, dict) else None
                if not isinstance(links, dict):
                    violations.append(f"{method.upper()} {path}: missing success response links")
                else:
                    for link_name in required_links:
                        if link_name not in links:
                            rendered = (
                                f"{method.upper()} {path}: "
                                f"missing success response link {link_name}"
                            )
                            violations.append(rendered)

        for status_code in ("400", "401", "403", "404", "406", "422", "500"):
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
                    f"{method.upper()} {path}: {status_code} response "
                    "missing application/problem+json"
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
