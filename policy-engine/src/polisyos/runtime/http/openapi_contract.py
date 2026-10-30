"""Public http openapi contract module API."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable  # noqa: TC003 - public map type is introspected
from copy import deepcopy
from datetime import UTC, datetime
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from pydantic import TypeAdapter

from polisyos.core import artifacts as core_artifacts
from polisyos.core.contracts import (
    CapabilityDiscoveryResponse,
    DecisionValidityStatus,
    EpochValidityBatchReceipt,
    EpochValidityBatchResponse,
    EpochValidityBatchTarget,
)
from polisyos.core.contracts.runtime import (
    EngineeringCapabilityAbsenceView,
    EpochOpenWorldRiskView,
    EpochProjectionDenominatorView,
    EpochStalenessProjectionView,
    InstitutionalAuthorityAbsenceView,
    MethodMetricProjectionResponse,
    RuntimeApiProblem,
    TemporalScope,
    epoch_staleness_semantic_hash,
)
from polisyos.runtime.http._openapi_contract_helpers import (
    iter_openapi_operations,
    runtime_problem_example,
)
from polisyos.runtime.http.permissions import permissions_for_roles
from polisyos.runtime.http.security import PolicyOSRole
from polisyos.runtime.http.services.confidence_ledger_risk_spend_contracts import (
    AvailableConfidenceLedgerRiskSpendPacket,
    ConfidenceLedgerRiskSpendPacket,
)
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    HUMAN_DECISION_RECORD_V2,
    LAYER2_S7_DELEGATION_SCHEMA_VERSION,
    HumanDecisionRecord,
)

_ARTIFACT_ID_SAMPLE = "sha256:" + "a" * 64
_SHA_PLAN = "sha256:79b64d4f43928e6cd7f7ad678c195d07fc61be69d672e768c82958761c869e1d"
_SHA_RUN_PAPER = "sha256:853c83b344ea60db46f918623684ef2abe369e642a9843344af3661e205980fa"
_SHA_REGISTRY = "sha256:bdedb5a6471e6a1b3bd16ef5065570d33157d96788e0ebc2ca17a569f03921b8"
_SHA_METHOD = "sha256:08622409c86efbeb945e4bdbdea7585e8eaff6e380c450273bc5b41bcf3f0073"
_SHA_ATLAS_PLAN = "sha256:35c1b64c91aa4209cffed4aed42d89258e5f975afab44464f201111ba0b4d725"
_SHA_DATA = "sha256:e79b613f05a6ebf356616cf97caa7b0e4d2dd15853974c3a76251a44ee0222fb"
_SHA_BINDINGS = "sha256:e823430756f9bab004490a705c8baa7b2e0f441d82d5703239b2cfff3bf264e4"
_SHA_LINEAGE = "sha256:0713f136ea316c8f3e274d55012e3bf10d05b5263837187a39593ff0d8838dfa"
_RUN_ID_SAMPLE = "R_core_api_001"
_REQUEST_ID_SAMPLE = "req_0123456789abcdef"
_TS_SAMPLE = "2026-02-11T12:00:00Z"
_CONFIDENCE_LEDGER_RISK_SPEND_OPENAPI_EXAMPLE_SHA256 = (
    "944918b3935fe325ac0b06ec005f71f6efe185bc5b36af808e3314132853232d"
)
_SCHEMA_COMPATIBILITY_ALIASES = {
    "ArtifactID": "ArtifactID-Input",
    "RunPaperDesignRecordBinding": "RunBoundDesignRecordBinding",
}
_ANALYST_PERMISSION_EXAMPLE = [
    permission.value for permission in permissions_for_roles([PolicyOSRole.ANALYST])
]
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
        {
            "kind": "result",
            "label": "scientist.decision_packet",
            "id": _ARTIFACT_ID_SAMPLE,
        },
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
_CYCLE_BOARD_COMPOSED_ABSENCE_SAMPLE = {
    "packet_schema_version": "policyos.runtime.cycle_board_packet.v1",
    "projection_id": "depth-n-cycle-board",
    "projection_rule_version": "policyos.runtime.depth_n_cycle_board.v2",
    "intended_audiences": ["REVIEWER", "EXPERT"],
    "composition_manifest": [
        {
            "source_id": "depth-n-cycle-board",
            "source_kind": "governed_projection",
            "source_ref": (
                "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json"
            ),
            "availability": "invalid_source",
            "artifact_content_hash": _SHA_DATA,
            "source_dependency_hash": None,
            "as_of": None,
            "freshness": None,
            "authoritative_for": [
                "cycle_board_domain_runs",
                "terminal_distributions",
                "recorded_evidence_classes",
            ],
            "may_not_use_for": [
                "public_claim",
                "publication_authority",
                "audience_authorization",
                "recompute_generation_cycle_semantics",
            ],
            "absence_reason": "owner validation is unavailable in this environment",
        },
        {
            "source_id": "n13a-acquisition-census",
            "source_kind": "governed_projection",
            "source_ref": (
                "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
            ),
            "availability": "invalid_source",
            "artifact_content_hash": _SHA_METHOD,
            "source_dependency_hash": None,
            "as_of": None,
            "freshness": None,
            "authoritative_for": [
                "acquisition_family_scorecards",
                "metric_resolution",
                "route_evidence",
            ],
            "may_not_use_for": [
                "public_claim",
                "publication_authority",
                "audience_authorization",
                "closeout_pass",
            ],
            "absence_reason": "owner validation is unavailable in this environment",
        },
        {
            "source_id": "n13a-live-probe-journal",
            "source_kind": "governed_projection",
            "source_ref": (
                "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json"
            ),
            "availability": "artifact_missing",
            "artifact_content_hash": None,
            "source_dependency_hash": None,
            "as_of": None,
            "freshness": None,
            "authoritative_for": [
                "live_probe_records",
                "family_receipts",
                "selection_plan",
            ],
            "may_not_use_for": [
                "public_claim",
                "publication_authority",
                "audience_authorization",
                "source_success_inference",
            ],
            "absence_reason": "the optional live-probe journal is absent",
        },
        {
            "source_id": "legacy-proving-ground",
            "source_kind": "governed_projection",
            "source_ref": "tests/fixtures/universal-corpus/manifest.json",
            "availability": "artifact_missing",
            "artifact_content_hash": None,
            "source_dependency_hash": None,
            "as_of": None,
            "freshness": None,
            "authoritative_for": [
                "legacy_case_identity",
                "fixture_semantic_expectation",
            ],
            "may_not_use_for": [
                "public_claim",
                "publication_authority",
                "audience_authorization",
                "readiness",
                "runtime_outcome",
                "admissibility",
            ],
            "absence_reason": "validator-confirmed legacy runtime outcomes are absent",
        },
        {
            "source_id": "surface-readiness",
            "source_kind": "governed_projection",
            "source_ref": "architecture/atlas_surfaces/surface-readiness-ledger.json",
            "availability": "artifact_missing",
            "artifact_content_hash": None,
            "source_dependency_hash": None,
            "as_of": None,
            "freshness": None,
            "authoritative_for": ["validated_surface_readiness_entries"],
            "may_not_use_for": [
                "public_claim",
                "publication_authority",
                "audience_authorization",
                "derive_readiness_from_route_presence",
            ],
            "absence_reason": "the governed readiness source is absent",
        },
        {
            "source_id": "n13b-global-deeper-terminal",
            "source_kind": "control_plane_evidence",
            "source_ref": (
                "architecture/policy_design_case/layer3_gy_n13b_acquisition_executor_contract.json"
            ),
            "availability": "artifact_missing",
            "artifact_content_hash": None,
            "source_dependency_hash": None,
            "as_of": None,
            "freshness": None,
            "authoritative_for": [],
            "may_not_use_for": [
                "per_row_movement",
                "row_enumeration",
                "exhaustiveness",
            ],
            "absence_reason": "the optional N13b control-plane artifact is absent",
        },
        {
            "source_id": "ds4-realized-disposition",
            "source_kind": "historical_owner_record",
            "source_ref": (
                "docs/plans/active/atlas-slices/DS4-status-grammar-rebinding-closure.md"
            ),
            "availability": "available",
            "artifact_content_hash": _SHA_DATA,
            "source_dependency_hash": None,
            "as_of": None,
            "freshness": None,
            "authoritative_for": ["historical_ds4_component_disposition"],
            "may_not_use_for": ["current_readiness", "current_producer_availability"],
            "absence_reason": None,
        },
        {
            "source_id": "historical-producer-availability",
            "source_kind": "historical_owner_record",
            "source_ref": (
                "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md"
            ),
            "availability": "available",
            "artifact_content_hash": _SHA_ATLAS_PLAN,
            "source_dependency_hash": None,
            "as_of": None,
            "freshness": None,
            "authoritative_for": ["historical_environment_relative_measurement"],
            "may_not_use_for": ["current_readiness", "current_producer_availability"],
            "absence_reason": None,
        },
    ],
    "composition_manifest_hash": (
        "sha256:46d37f06014cff1f291cf91b2114a67485f2fc5e6f2e6c241a41474f2b978650"
    ),
    "source_dependency_hash": (
        "sha256:48105c74bc9fe5655d331f48ce489ee852262ba18893373f28f407e928e83fd3"
    ),
    "projection_hash": ("sha256:34e48f97cabfe5c5596d1842b10687ff61498d90123cc9633849bea303d1e7dd"),
    "projection_observed_at": _TS_SAMPLE,
    "stable_address": "/api/v1/exports/governed-projections/depth-n-cycle-board",
    "replay_address": (
        "/api/v1/exports/governed-projections/depth-n-cycle-board?composition_m"
        "anifest_hash=sha256%3A46d37f06014cff1f291cf91b2114a67485f2fc5e6f2e6c24"
        "1a41474f2b978650&projection_hash=sha256%3A34e48f97cabfe5c5596d1842b106"
        "87ff61498d90123cc9633849bea303d1e7dd&projection_rule_version=policyos."
        "runtime.depth_n_cycle_board.v2&replay_target=composed_v2&source_depend"
        "ency_hash=sha256%3A48105c74bc9fe5655d331f48ce489ee852262ba18893373f28f"
        "407e928e83fd3"
    ),
    "payload": {
        "rows": [],
        "coverage": {
            "capability_state": "absent/unallocated",
            "deficits": ["artifact_missing", "bridge_missing"],
            "missing_link": "production_recursive_cycle_run_enumeration",
            "owner_route": "GY-GAP5 -> runtime/quality GY-N12",
            "execution_status": "not_established",
            "known_scope": "N10 capstone + legacy fixture cohort",
            "unknown_scope": "future production recursive-cycle DesignProblems",
            "known_row_count": 0,
            "exhaustive": False,
        },
        "movement_gap": {
            "capability_state": "absent/unallocated",
            "deficits": ["artifact_missing", "bridge_missing"],
            "missing_link": "acquisition_reentry_deeper_terminal_binding",
            "producer_route": "GY-GAP6 -> GY-N13b",
            "chronology_route": "GY-N12",
            "execution_status": "not_established",
            "movement_records": [],
        },
        "realized_ds4_disposition": {
            "source_class": "historical_ds4_component_disposition",
            "source_ref": (
                "docs/plans/active/atlas-slices/DS4-status-grammar-rebinding-closure.md"
            ),
            "source_content_hash": _SHA_DATA,
            "counts": {"package": 27, "rebind": 41, "use_as_is": 18, "retire": 3},
            "denominator": 89,
        },
        "historical_producer_availability": {
            "source_ref": (
                "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md"
            ),
            "source_content_hash": _SHA_ATLAS_PLAN,
            "read_receipt": {
                "source_ref": (
                    "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md"
                ),
                "read_status": "read",
                "status": "COMPLETE",
                "coverage": "complete_selected_input",
                "source_content_hash": _SHA_ATLAS_PLAN,
                "read_error": None,
                "table_row_denominator": 172,
                "selected_measurement_cell_count": 1,
                "selector": "all_markdown_table_cells_with_ds3_measurement",
                "unresolved_by_construction": [
                    "non_table_sections_uninterpreted",
                    "other_sources_unselected",
                    "current_availability_not_measured",
                ],
            },
            "counts": {"available": 5, "invalid_source": 7, "artifact_missing": 1},
            "measurement_scope": "environment_relative",
            "environment_absence": "production_data",
        },
    },
}

_DEFAULT_PROBLEM_RESPONSES: dict[str, dict[str, str]] = {
    "400": {
        "code": "bad_request",
        "description": "Malformed request payload or parameters.",
    },
    "401": {
        "code": "unauthorized",
        "description": "Authentication is required for this route.",
    },
    "403": {
        "code": "forbidden",
        "description": "Authenticated principal cannot access this resource.",
    },
    "404": {"code": "not_found", "description": "Requested resource does not exist."},
    "406": {
        "code": "not_acceptable",
        "description": "Requested representation is not supported for this resource.",
    },
    "422": {
        "code": "request_validation_failed",
        "description": "Request validation failed.",
    },
    "500": {"code": "internal_error", "description": "Unexpected runtime API failure."},
}

_RUNTIME_PROBLEM_MEDIA_TYPE = "application/problem+json"
_RUNTIME_PROBLEM_SCHEMA_REF = "#/components/schemas/RuntimeApiProblem"

_SUCCESS_LINKS_BY_OPERATION: dict[str, dict[str, dict[str, Any]]] = {
    "get_artifact_manifest": {
        "artifactPreview": {
            "operationId": "get_artifact_content",
            "parameters": {
                "artifact_id": "$response.body#/artifact/artifact_id",
                "manifest_profile_sha256": "$response.body#/artifact/manifest_profile_sha256",
            },
            "description": "Fetch a preview or raw representation for the same artifact.",
        },
        "artifactDownload": {
            "operationId": "download_artifact_content",
            "parameters": {"artifact_id": "$response.body#/artifact/artifact_id"},
            "description": "Download the immutable binary payload for the same artifact.",
        },
        "artifactSchema": {
            "operationId": "get_artifact_schema",
            "parameters": {
                "artifact_id": "$response.body#/artifact/artifact_id",
                "manifest_profile_sha256": "$response.body#/artifact/manifest_profile_sha256",
            },
            "description": "Inspect the schema contract associated with the same artifact.",
        },
        "artifactLineage": {
            "operationId": "get_artifact_lineage",
            "parameters": {
                "artifact_id": "$response.body#/artifact/artifact_id",
                "manifest_profile_sha256": "$response.body#/artifact/manifest_profile_sha256",
            },
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

_RUN_PAPER_TYPED_UNAVAILABLE_SAMPLE = {
    "packet_schema_version": "policyos.runtime.run_paper_packet.v1",
    "projection_rule_version": "policyos.runtime.run_paper.v1",
    "intended_audiences": ["reviewer", "expert"],
    "run": {
        "run_id": _RUN_ID_SAMPLE,
        "source_kind": "core_run",
        "status": "completed",
        "run_terminality": "terminal",
        "started_at": None,
        "finished_at": None,
        "duration_ms": None,
        "tenant_id": "tenant-fixture",
        "cell_id": None,
    },
    "case_record": {
        "availability": "artifact_missing",
        "capability_state": "producer_missing",
        "reason_code": "case-record-not-run-bound",
        "owner_route": "team-runtime",
        "closure_signal": "case-record-not-run-bound",
        "may_not_use_for": [
            "case_identity",
            "design_record",
            "grounding_state",
            "admission_state",
            "promotion_state",
            "blockers",
            "limitations",
            "objections",
            "abstentions",
        ],
    },
    "stage_trace": {
        "availability": "not_established",
        "reason": "verified run manifest carries no trace reference",
        "owner_route": "core RunManifest.trace_ref",
    },
    "artifact_links": [],
    "source": {
        "manifest_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "core.run_manifest",
            "media_type": "application/json",
        },
        "manifest_schema_name": "polisyos.core.RunManifest",
        "manifest_schema_version": "0.1.0",
        "producer": None,
        "environment": None,
        "registry_bundle": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "core.registry_bundle",
            "media_type": "application/json",
        },
    },
    "replay_pins": {
        "manifest_artifact_id": _ARTIFACT_ID_SAMPLE,
        "manifest_schema_version": "0.1.0",
        "paper_projection_rule_version": "policyos.runtime.run_paper.v1",
        "paper_projection_hash": _SHA_RUN_PAPER,
    },
    "projection_hash": _SHA_RUN_PAPER,
    "stable_address": f"/api/v1/runs/{_RUN_ID_SAMPLE}/paper",
    "replay_address": (
        f"/api/v1/runs/{_RUN_ID_SAMPLE}/paper?manifest_artifact_id="
        f"{_ARTIFACT_ID_SAMPLE.replace(':', '%3A')}"
        "&manifest_schema_version=0.1.0&paper_projection_hash="
        f"{_SHA_RUN_PAPER.replace(':', '%3A')}"
        "&paper_projection_rule_version=policyos.runtime.run_paper.v1"
    ),
    "report_href": (
        f"/runs/{_RUN_ID_SAMPLE}/report?manifest_artifact_id="
        f"{_ARTIFACT_ID_SAMPLE.replace(':', '%3A')}"
        "&manifest_schema_version=0.1.0&paper_projection_hash="
        f"{_SHA_RUN_PAPER.replace(':', '%3A')}"
        "&paper_projection_rule_version=policyos.runtime.run_paper.v1"
        "#stage-trace"
    ),
}


_HUMAN_DECISION_PREDICATE_SAMPLE = (
    ("identity_permission", "recomputed"),
    ("role_mandate_or_basis", "independently_reconciled"),
    ("operation_accountability", "recomputed"),
    ("currentness", "recomputed"),
    ("right_decision_time", "recomputed"),
    ("reviewer_independence_change", "independently_reconciled"),
    ("evidence_exposure", "independently_reconciled"),
    ("presentation_format_channel", "independently_reconciled"),
    ("source_producer_trust", "independently_reconciled"),
)
_HUMAN_DECISION_RECORD_SAMPLE: dict[str, Any] = {
    "schema_version": "policyos.runtime.human_decision_record.v2",
    "record_id": "human-decision-openapi-sample",
    "record_ref": "runtime://human-decisions/openapi-sample",
    "case_id": "case-openapi-sample",
    "human_decision_request_ref": "runtime://human-decisions/requests/openapi-sample",
    "actor_ref": "principal://reviewer/openapi-sample",
    "actor_role": "mandate_owner",
    "decided_at": _TS_SAMPLE,
    "decision_action_exercised": "approve",
    "evidence_summary_ref": "runtime://human-decisions/evidence/openapi-sample",
    "disconfirming_evidence_refs": [_SHA_DATA],
    "active_choice": True,
    "accountability_statement": "I accept accountability for this bounded decision.",
    "mandate_record_ref": "mandate://openapi-sample",
    "mandate_source_refs": [_SHA_PLAN],
    "five_rights_check": {
        "right_decision": True,
        "right_person": True,
        "right_information": True,
        "right_format_channel": True,
        "right_time": True,
    },
    "responsibility_integrity": {
        "status": "pass",
        "pattern_ids": ["P26", "P05", "P37"],
        "reason": "All nine gate predicates were recomputed or independently reconciled.",
        "missing_requirements": [],
        "rule_version_ref": "policyos.runtime.human-decision.openapi.v1",
    },
    "authority_boundary": {
        "authoritative_for": ["human_decision_act"],
        "may_not_use_for": ["policyos_custody_signature", "publication_authority"],
        "source_authority": "human_governance",
        "posture": "governed",
        "rule_version_refs": ["policyos.runtime.human-decision.openapi.v1"],
        "known_limits": [],
    },
    "provenance_refs": [_ARTIFACT_ID_SAMPLE, _SHA_PLAN],
    "rule_version_ref": "policyos.runtime.human-decision.openapi.v1",
    "created_at": _TS_SAMPLE,
    "tenant_id": "tenant-openapi-sample",
    "run_id": _RUN_ID_SAMPLE,
    "decision_attempt_id": "human-decision-attempt-openapi-sample",
    "governed_action_key": _SHA_BINDINGS,
    "binding_sha256": _SHA_METHOD,
    "source_kind": "agent_action_authority",
    "source_ref": _ARTIFACT_ID_SAMPLE,
    "source_digest": _ARTIFACT_ID_SAMPLE,
    "decision_request_digest": _SHA_RUN_PAPER,
    "basis_ref": _SHA_PLAN,
    "basis_digest": _SHA_PLAN,
    "principal_binding_ref": _SHA_REGISTRY,
    "principal_binding_digest": _SHA_REGISTRY,
    "reviewer_separation_ref": _SHA_METHOD,
    "reviewer_separation_digest": _SHA_METHOD,
    "presentation_contract_ref": _SHA_DATA,
    "presentation_contract_digest": _SHA_DATA,
    "exposure_session_ref": _SHA_BINDINGS,
    "exposure_session_digest": _SHA_BINDINGS,
    "canonical_actor": {
        "issuer": "institution://identity/openapi-sample",
        "audience": "polisyos-runtime",
        "subject": "reviewer-openapi-sample",
        "tenant_id": "tenant-openapi-sample",
        "actor_ref": "principal://reviewer/openapi-sample",
        "signing_key_id": _SHA_LINEAGE,
        "signed_roles": ["mandate_owner"],
    },
    "decision_mode": "ordinary",
    "dissent_statement": "Disconfirming evidence was reviewed and retained.",
    "override_reason": None,
    "blocking_reason": None,
    "predicate_receipts": [
        {
            "predicate": predicate,
            "satisfied": True,
            "provenance": provenance,
            "evidence_refs": [_ARTIFACT_ID_SAMPLE],
            "reason_code": f"DS9-OPENAPI-{predicate.upper().replace('_', '-')}",
            "reason": f"{predicate} passed against exact signed inputs.",
            "rule_version_ref": "policyos.runtime.human-decision.openapi.v1",
        }
        for predicate, provenance in _HUMAN_DECISION_PREDICATE_SAMPLE
    ],
    "exposure_event_refs": [_SHA_DATA],
    "exposure_artifact_digests": [_SHA_PLAN],
    "verifier_epoch": "openapi-sample-epoch",
    "requested_at": _TS_SAMPLE,
    "observed_at": _TS_SAMPLE,
    "recorded_at": _TS_SAMPLE,
    "valid_from": _TS_SAMPLE,
    "valid_until": "2026-02-11T13:00:00Z",
    "reservation_id": "human-decision-reservation-openapi-sample",
    "reservation_version": 1,
    "custody_signer_identity": "service://runtime/human-decision-custody",
    "custody_key_id": _SHA_RUN_PAPER,
    "custody_boundary": {
        "authoritative_for": ["human_decision_record_custody"],
        "may_not_use_for": ["human_signature", "publication_authority"],
        "source_authority": "deterministic_producer",
        "posture": "governed",
        "rule_version_refs": ["policyos.runtime.human-decision.openapi.v1"],
        "known_limits": [],
    },
}
_HUMAN_DECISION_CREATE_SAMPLE = {
    "run_id": _RUN_ID_SAMPLE,
    "record_ref": _SHA_RUN_PAPER,
    "record_digest": _SHA_RUN_PAPER,
    "record": _HUMAN_DECISION_RECORD_SAMPLE,
    "durable_event_id": "event-human-decision-openapi-sample",
    "reservation_id": "human-decision-reservation-openapi-sample",
    "reservation_version": 1,
}


def _capability_discovery_example(
    posture: str,
) -> dict[str, Any]:
    resource_kind = "case" if posture == "case_producer_missing" else "method"
    if posture == "no_hit_incomplete":
        resource_kind = "dataset"
    request = {
        "search": {
            "request_id": f"search:openapi:{posture}",
            "query_text": "generated capability",
            "construct_refs": ["construct:generated"],
            "intent": "capability_discovery",
            "required_layers": ["runtime_registry"],
            "authority_purpose": "review_capability_candidates",
            "allowed_modes": ["exact"],
            "budget": {"top_k": 5},
            "rule_version": "policyos.ds10.discovery.v1",
        },
        "resource_kinds": [resource_kind],
        "audience": "REVIEWER",
    }
    time = {
        "observed_at": _TS_SAMPLE,
        "valid_from": _TS_SAMPLE,
        "valid_until": "2026-02-11T13:00:00Z",
        "freshness": "current",
    }
    has_result = posture in {
        "discoverable_executable_authority_not_established",
        "candidate_only",
    }
    candidate_ref = "capability:method:generated"
    candidate = {
        "candidate_ref": candidate_ref,
        "source_layer": "owner",
        "match_mode": "exact",
        "score": 0.9,
        "evidence_refs": ["evidence:method:owner"],
        "limitation_refs": [],
        "authority_boundary": {"authoritative_for": []},
        "may_not_use_for": ["publication_authority"],
    }
    if posture == "case_producer_missing":
        completeness_status = "producer_missing"
        reasons = ["case:producer_missing"]
    elif posture == "no_hit_incomplete":
        completeness_status = "recall_unmeasured"
        reasons = ["dataset:recall_unmeasured"]
    else:
        completeness_status = "complete"
        reasons = []
    frontier = {
        "request_ref": request["search"]["request_id"],
        "query_plan": {"resource_kinds": [resource_kind]},
        "corpus_ref": "runtime-quality:capability-provider-registry",
        "corpus_path": "runtime/quality/capability_discovery.py",
        "corpus_snapshot_hash": "sha256:" + "1" * 64,
        "corpus_kind": "canonical",
        "configured_store_path": None,
        "indexes_used": ["index:capability-owner"],
        "index_version_refs": ["snapshot:capability-owner"],
        "index_freshness": {"index:capability-owner": {"state": "current"}},
        "query_expansion_traces": [],
        "candidates": [candidate] if has_result else [],
        "rejected_candidates": [],
        "no_hit_frontier": [] if has_result else [resource_kind],
        "incompleteness": {"status": completeness_status},
        "replay_key": f"capability-discovery:openapi:{posture}",
        "replay_command": "python -m polisyos.runtime.quality.capability_discovery --help",
        "replay_expected_output_hash": "sha256:" + "2" * 64,
        "requested_count": 5,
        "evaluated_count": 1 if has_result else 0,
        "returned_count": 1 if has_result else 0,
        "actual_cutoff": None,
        "completeness_status": completeness_status,
        "incompleteness_reasons": reasons,
    }
    results: list[dict[str, Any]] = []
    if has_result:
        executable = posture == "discoverable_executable_authority_not_established"
        authority_state = "not_established" if executable else "candidate_only"
        results.append(
            {
                "capability_ref": candidate_ref,
                "content_digest": "sha256:" + "3" * 64,
                "resource_kind": "method",
                "label": "Generated method",
                "description": "Owner-projected candidate for posture illustration.",
                "discovery_result": {
                    "state": "discoverable",
                    "producer_ref": "producer:method:owner",
                    "snapshot_ref": "snapshot:method:owner",
                    "freshness_ref": "freshness:method:owner",
                    "reason_codes": [],
                    "provenance_refs": ["provenance:method:owner"],
                    "time": time,
                },
                "execution_result": {
                    "state": "executable" if executable else "not_established",
                    "producer_ref": "runtime-quality:capability-execution-reconciler",
                    "operation_ref": "operation:method:owner" if executable else None,
                    "conformance_ref": "conformance:method:owner" if executable else None,
                    "policy_ref": "policy:method:enabled" if executable else None,
                    "reason_codes": []
                    if executable
                    else ["live_operation_registry_not_established"],
                    "provenance_refs": ["provenance:method:owner"],
                    "time": time,
                },
                "authority_result": {
                    "state": authority_state,
                    "producer_ref": "runtime-quality:capability-authority-composer",
                    "authority_purpose": "review_capability_candidates",
                    "binding_ref": None,
                    "currentness_ref": None,
                    "reason_codes": [
                        "not_established",
                        "owner_binding_producer_missing",
                    ],
                    "provenance_refs": ["policyos.ds10.capability_authority.v1"],
                    "time": time,
                },
                "authoritative_for": [],
                "may_not_use_for": [
                    "publication_authority",
                    "discovery_as_execution_authority",
                ],
                "authority_purpose": "review_capability_candidates",
                "provenance_refs": [
                    "provenance:method:owner",
                    "policyos.ds10.capability_authority.v1",
                ],
                "rule_version": "policyos.ds10.discovery.v1",
                "time": time,
            }
        )
    packet = CapabilityDiscoveryResponse.model_validate(
        {
            "meta": _META_NO_SOURCE,
            "request": request,
            "request_digest": "sha256:" + "4" * 64,
            "authority_purpose": "review_capability_candidates",
            "audience": "REVIEWER",
            "results": results,
            "frontier": frontier,
            "rule_version": "policyos.ds10.discovery.v1",
            "provenance_refs": ["runtime-quality:capability-provider-registry"],
            "time": time,
        }
    )
    return packet.model_dump(mode="json")


_CAPABILITY_DISCOVERY_SUCCESS_EXAMPLES = {
    posture: {
        "summary": posture.replace("_", " "),
        "value": _capability_discovery_example(posture),
    }
    for posture in (
        "discoverable_executable_authority_not_established",
        "candidate_only",
        "no_hit_incomplete",
        "case_producer_missing",
    )
}


def _epoch_staleness_example(*, fixture_only: bool) -> dict[str, Any]:
    packet_ref = core_artifacts.ArtifactRef(
        artifact_id=_ARTIFACT_ID_SAMPLE,
        kind="scientist.decision_packet",
        media_type="application/json",
    )
    scope = TemporalScope.model_validate(_TEMPORAL_SCOPE_SAMPLE)
    engineering = EngineeringCapabilityAbsenceView(
        missing_output=(
            "An owner-emitted epoch-inheritance/recompute-status projection and its "
            "temporal read bridge."
        ),
        consequence=("Dependent derivations remain stale with recompute_status=not_established."),
        closure_condition=(
            "Implement the producer/read bridge in the named candidate owner module."
        ),
    )
    institutional = ()
    status = "current"
    current_epoch_ref = "sha256:" + "c" * 64
    predicate_provenance = "independently_reconciled"
    denominator = EpochProjectionDenominatorView(
        predicate_provenance="independently_reconciled",
        denominator_ref="sha256:" + "d" * 64,
        source_count=2,
        target_count=3,
    )
    limitations = ("derived_recompute_status_not_established",)
    owner_as_of = datetime(2026, 2, 11, 12, 0, tzinfo=UTC)
    owner_time_reason = None
    if not fixture_only:
        status = "not_established"
        current_epoch_ref = None
        predicate_provenance = "not_established"
        denominator = EpochProjectionDenominatorView(predicate_provenance="not_established")
        institutional = (
            InstitutionalAuthorityAbsenceView(
                role="epoch_predicate_policy_signer",
                authority_purpose="semantic_epoch_qualification",
                refusal_code="policy_admission_missing",
                consequence="Epoch currentness and publication are not established.",
                closure_condition=(
                    "Institutional appointment may occur after real-user deployment; "
                    "DS18 closes on truthful refusal rendering."
                ),
                inspectable_capabilities=("history", "candidate", "replay", "MACHINE"),
            ),
            InstitutionalAuthorityAbsenceView(
                role="epoch_transition_signer",
                authority_purpose="epoch_transition_issuance",
                refusal_code="epoch_transition_signer_not_established",
                consequence="Transition issuance is unavailable and promotion stays frozen.",
                closure_condition=(
                    "Institutional appointment may occur after real-user deployment; "
                    "DS18 closes on useful typed refusal rendering."
                ),
                inspectable_capabilities=(
                    "history",
                    "stale_bindings",
                    "replay",
                    "MACHINE",
                ),
            ),
        )
        limitations = (
            "epoch_dependency_denominator_not_established",
            "policy_admission_missing",
            "epoch_transition_signer_not_established",
            "derived_recompute_status_not_established",
        )
        owner_as_of = None
        owner_time_reason = "owner_time_not_established"
    draft = EpochStalenessProjectionView.model_construct(
        run_id=_RUN_ID_SAMPLE,
        decision_packet_ref=packet_ref,
        temporal_scope=scope,
        requested_query_context_ref="sha256:" + "b" * 64,
        owner_as_of=owner_as_of,
        owner_time_reason=owner_time_reason,
        observed_at=datetime(2026, 2, 11, 12, 2, tzinfo=UTC),
        status=status,
        current_epoch_ref=current_epoch_ref,
        scoped_epoch_refs=((current_epoch_ref,) if current_epoch_ref is not None else ()),
        decision_validity_status=(DecisionValidityStatus.ACTIVE if fixture_only else None),
        revalidation_required=False,
        denominator=denominator,
        certificates=(),
        dependencies=(),
        perturbations=(),
        lineage=(),
        open_world_risk=EpochOpenWorldRiskView(
            status=("established" if fixture_only else "not_established"),
            limitation_code=(
                "all_components_within_scope" if fixture_only else "open_world_vector_unresolved"
            ),
            promotion_frozen=not fixture_only,
        ),
        institutional_absences=institutional,
        engineering_absences=(engineering,),
        limitations=limitations,
        predicate_provenance=predicate_provenance,
        fixture_only=fixture_only,
        projection_semantic_hash="sha256:" + "0" * 64,
    )
    projection = EpochStalenessProjectionView.model_validate(
        {
            **draft.model_dump(mode="json"),
            "projection_semantic_hash": epoch_staleness_semantic_hash(draft),
        }
    )
    return {
        "meta": _META_CORE_RUN,
        "projection": projection.model_dump(mode="json"),
    }


def _epoch_validity_batch_example() -> dict[str, Any]:
    transition_ref = core_artifacts.ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="chronology.epoch_transition",
        media_type="application/vnd.polisyos.chronology+json",
    )
    target = EpochValidityBatchTarget(
        packet_ref="sha256:" + "2" * 64,
        decision_lineage_key="lineage-openapi-epoch-batch",
        dependency_key="law:openapi-epoch-batch",
        status=DecisionValidityStatus.REVIEW_REQUIRED,
        reason="A content-bound epoch transition requires packet revalidation.",
    )
    receipt = EpochValidityBatchReceipt(
        batch_id="epoch-batch-openapi-sample",
        transition_artifact_ref=transition_ref,
        transition_content_hash=str(transition_ref.artifact_id),
        requested_query_context_ref="sha256:" + "3" * 64,
        dependency_denominator_ref="sha256:" + "4" * 64,
        adjudication_denominator_ref="sha256:" + "5" * 64,
        verifier_provenance_ref=core_artifacts.ArtifactRef(
            artifact_id="sha256:" + "6" * 64,
            kind="chronology.epoch_transition_verification_receipt",
            media_type="application/json",
        ),
        completion_receipt_ref=core_artifacts.ArtifactRef(
            artifact_id="sha256:" + "7" * 64,
            kind="decision_validity.epoch_batch_completion",
            media_type="application/json",
        ),
        affected_packet_refs=(target.packet_ref,),
        targets=(target,),
    )
    return EpochValidityBatchResponse(
        meta=_META_NO_SOURCE,
        batch_id=receipt.batch_id,
        state="completed",
        transition=transition_ref,
        completion_receipt=receipt,
        affected_packet_refs=receipt.affected_packet_refs,
    ).model_dump(mode="json")


# Captured from the actual worker -> later-signed HTTP fixture, without changing
# response values. See the PA1 openapi-response-capture command and provenance.
# This documentation sample is never read by runtime evidence admission.
_NORMATIVE_EVIDENCE_FIXTURE_RESPONSE: dict[str, Any] = {
    "status": "admitted",
    "head_ref": ("sha256:d7d43f5969fe8c96c135717ccc6772cab4a7ddfe36de6ceea2601a50830a6100"),
    "attempted_disposition_ref": (
        "sha256:5feaacea427178b78e4c1a56f748060d2bb27b728ac0062470d7655ffa087bb0"
    ),
    "job": {
        "meta": {
            "request_id": "ee06ef9ea7974052b729bb8962bd0874",
            "generated_at": "2026-09-08T11:14:34.701964Z",
            "source_kinds": [],
        },
        "job_id": "1c4fa4a02a7f48bcb1b91be75093a229",
        "kind": "natural_language_run",
        "state": "completed",
        "run_id": "R_9bfa9624a0a11eef",
        "pipeline_id": None,
        "requested_execution_profile": None,
        "effective_execution_profile": "dev",
        "capability_manifest_ref": {
            "artifact_id": (
                "sha256:ba4ce3c08d828641c6d4c09c4610961af2b3c59330632ea769750559302474f6"
            ),
            "kind": "runtime.capability_manifest",
            "media_type": "application/json",
        },
        "submitted_at": "2026-09-08T11:14:32Z",
        "started_at": None,
        "finished_at": "2026-09-08T11:14:32Z",
        "error_message": None,
        "failure": None,
        "execution_status": "completed",
        "quality_status": "warn",
        "quality_scorecard_ref": None,
        "authoritative_scorecard_ref": None,
        "projection_source": {
            "source_surface": "runtime.control_job",
            "source_detail": "control_store_progress",
            "authority_level": "projection_only",
            "projection_policy": "projection_only",
        },
        "runtime_state": "completed",
        "approval_projection": {
            "state": None,
            "eligible": False,
            "reasons": ["authority_surface_signal_missing"],
            "source_surface": "runtime.control_job",
            "authority_level": "projection_only",
        },
        "unresolved_authority_gaps": [
            {
                "code": "authority_surface_signal_missing",
                "layer": "runtime_authority_surface",
                "phase": "run_status",
                "message": (
                    "Run status consumed AuthorityBoundary and cannot"
                    " be treated as authority for runtime_closeout_au"
                    "thority: blocked."
                ),
                "owner": "team-runtime-quality",
                "evidence_ref": None,
                "next_action": (
                    "Repair workflow failure or rerun through the workspace loop authority path."
                ),
                "next_diagnostic_command": (
                    "python3 tools/quality/validation/check_layer3_wo"
                    "rkflow_failure_authority.py --check --repo-root "
                    "."
                ),
            }
        ],
        "next_diagnostic_commands": [
            (
                "python3 tools/quality/validation/check_layer3_wo"
                "rkflow_failure_authority.py --check --repo-root "
                "."
            )
        ],
        "policy_design_case_projection": None,
        "quality_evidence_bundle_path": None,
        "quality_gates": [
            {
                "name": "normative_evidence_present",
                "code": ("normative_applicability_report_ref_optional_missing"),
                "status": "warn",
                "layer": "lex",
                "phase": "quality_evidence",
                "message": (
                    "Normative applicability evidence is present. Run"
                    "time-owned normative_applicability_report_ref is"
                    " missing."
                ),
                "evidence_ref": None,
                "next_action": (
                    "Persist normative_applicability_report_ref from "
                    "the owning runtime layer before production appro"
                    "val."
                ),
                "next_diagnostic_command": None,
                "blocking": False,
                "operator_diagnostic": None,
            },
            {
                "name": "fabric_retrieval_trace_present",
                "code": "fabric_retrieval_trace_ref_optional_missing",
                "status": "warn",
                "layer": "fabric_retrieval",
                "phase": "quality_evidence",
                "message": (
                    "Fabric source-selection evidence is present. Run"
                    "time-owned fabric_retrieval_trace_ref is missing"
                    "."
                ),
                "evidence_ref": None,
                "next_action": (
                    "Persist fabric_retrieval_trace_ref from the owni"
                    "ng runtime layer before production approval."
                ),
                "next_diagnostic_command": None,
                "blocking": False,
                "operator_diagnostic": None,
            },
            {
                "name": "foundry_method_evidence_present",
                "code": "foundry_method_report_ref_optional_missing",
                "status": "warn",
                "layer": "foundry_methods",
                "phase": "quality_evidence",
                "message": (
                    "Foundry method validity evidence is present. Run"
                    "time-owned foundry_method_report_ref is missing."
                ),
                "evidence_ref": None,
                "next_action": (
                    "Persist foundry_method_report_ref from the ownin"
                    "g runtime layer before production approval."
                ),
                "next_diagnostic_command": None,
                "blocking": False,
                "operator_diagnostic": None,
            },
            {
                "name": "policy_grounding_matrix_present",
                "code": "policy_grounding_matrix_ref_optional_missing",
                "status": "warn",
                "layer": "scientist_policy_artifacts",
                "phase": "quality_evidence",
                "message": (
                    "Policy grounding matrix is present. Runtime-owne"
                    "d policy_grounding_matrix_ref is missing."
                ),
                "evidence_ref": None,
                "next_action": (
                    "Persist policy_grounding_matrix_ref from the own"
                    "ing runtime layer before production approval."
                ),
                "next_diagnostic_command": None,
                "blocking": False,
                "operator_diagnostic": None,
            },
            {
                "name": "conflict_check_present",
                "code": "conflict_check_ref_optional_missing",
                "status": "warn",
                "layer": "normative_conflict",
                "phase": "quality_evidence",
                "message": (
                    "Policy conflict check is present. Runtime-owned conflict_check_ref is missing."
                ),
                "evidence_ref": None,
                "next_action": (
                    "Persist conflict_check_ref from the owning runti"
                    "me layer before production approval."
                ),
                "next_diagnostic_command": None,
                "blocking": False,
                "operator_diagnostic": None,
            },
            {
                "name": "causal_statistical_validity_present",
                "code": ("causal_statistical_validity_report_ref_optional_missing"),
                "status": "warn",
                "layer": "foundry_causal_validity",
                "phase": "quality_evidence",
                "message": (
                    "Causal/statistical validity benchmark evidence i"
                    "s present. Runtime-owned causal_statistical_vali"
                    "dity_report_ref is missing."
                ),
                "evidence_ref": None,
                "next_action": (
                    "Persist causal_statistical_validity_report_ref f"
                    "rom the owning runtime layer before production a"
                    "pproval."
                ),
                "next_diagnostic_command": None,
                "blocking": False,
                "operator_diagnostic": None,
            },
            {
                "name": "replay_manifest_present",
                "code": "replay_manifest_ref_optional_missing",
                "status": "warn",
                "layer": "runtime_replay",
                "phase": "quality_evidence",
                "message": (
                    "Deterministic replay manifest is present. Runtim"
                    "e-owned replay_manifest_ref is missing."
                ),
                "evidence_ref": None,
                "next_action": (
                    "Persist replay_manifest_ref from the owning runt"
                    "ime layer before production approval."
                ),
                "next_diagnostic_command": None,
                "blocking": False,
                "operator_diagnostic": None,
            },
            {
                "name": "drift_explanation_present",
                "code": "drift_explanation_ref_optional_missing",
                "status": "warn",
                "layer": "runtime_replay",
                "phase": "quality_evidence",
                "message": (
                    "Replay drift explanation evidence is present. Ru"
                    "ntime-owned drift_explanation_ref is missing."
                ),
                "evidence_ref": None,
                "next_action": (
                    "Persist drift_explanation_ref from the owning ru"
                    "ntime layer before production approval."
                ),
                "next_diagnostic_command": None,
                "blocking": False,
                "operator_diagnostic": None,
            },
            {
                "name": "resilience_matrix_present",
                "code": "resilience_report_ref_optional_missing",
                "status": "warn",
                "layer": "runtime_resilience",
                "phase": "quality_evidence",
                "message": (
                    "Load, soak, and resilience matrix evidence is pr"
                    "esent. Runtime-owned resilience_report_ref is mi"
                    "ssing."
                ),
                "evidence_ref": None,
                "next_action": (
                    "Persist resilience_report_ref from the owning ru"
                    "ntime layer before production approval."
                ),
                "next_diagnostic_command": None,
                "blocking": False,
                "operator_diagnostic": None,
            },
            {
                "name": "human_review_calibration_present",
                "code": ("human_review_calibration_report_ref_optional_missing"),
                "status": "warn",
                "layer": "human_review_calibration",
                "phase": "quality_evidence",
                "message": (
                    "Human-review calibration evidence is present. Ru"
                    "ntime-owned human_review_calibration_report_ref "
                    "is missing."
                ),
                "evidence_ref": None,
                "next_action": (
                    "Persist human_review_calibration_report_ref from"
                    " the owning runtime layer before production appr"
                    "oval."
                ),
                "next_diagnostic_command": None,
                "blocking": False,
                "operator_diagnostic": None,
            },
            {
                "name": "privacy_compliance_report_present",
                "code": "privacy_compliance_report_ref_optional_missing",
                "status": "warn",
                "layer": "privacy_compliance",
                "phase": "quality_evidence",
                "message": (
                    "Privacy, licensing, and compliance evidence is p"
                    "resent. Runtime-owned privacy_compliance_report_"
                    "ref is missing."
                ),
                "evidence_ref": None,
                "next_action": (
                    "Persist privacy_compliance_report_ref from the o"
                    "wning runtime layer before production approval."
                ),
                "next_diagnostic_command": None,
                "blocking": False,
                "operator_diagnostic": None,
            },
            {
                "name": "decision_artifact_quality_present",
                "code": ("decision_artifact_quality_report_ref_optional_missing"),
                "status": "warn",
                "layer": "scientist_decision_artifact",
                "phase": "quality_evidence",
                "message": (
                    "Decision-artifact quality evidence is present. R"
                    "untime-owned decision_artifact_quality_report_re"
                    "f is missing."
                ),
                "evidence_ref": None,
                "next_action": (
                    "Persist decision_artifact_quality_report_ref fro"
                    "m the owning runtime layer before production app"
                    "roval."
                ),
                "next_diagnostic_command": None,
                "blocking": False,
                "operator_diagnostic": None,
            },
        ],
        "blocking_quality_failures": [],
        "operator_diagnostic": None,
        "progress": {
            "compiled_recursive_generation_cycle_ref": (
                "sha256:65cefea4386572f6255089d2418cc43f9736c41227eb1352a351a80815b17458"
            ),
            "manifest_ref": (
                "sha256:c40e352f285fc6c9064f93ea1756815c2265f5ed5c0c2e5a214cc8e900141c84"
            ),
            "normative_disposition": {
                "schema_version": "policyos.normative_generation_composition.v1",
                "compiled_run_ref": (
                    "sha256:65cefea4386572f6255089d2418cc43f9736c41227eb1352a351a80815b17458"
                ),
                "leaf_disposition_refs": {
                    (
                        "design-problem://f59c8f38958da3790dff02aae047ee5"
                        "e0b86c3a5599535f0d6da93e73dfce57d"
                    ): ("sha256:bd8a730b5b2578439a8375ddbab1df52f432bac9b2bc0e65a8e09709c353f324")
                },
                "leaf_dispositions": {
                    (
                        "design-problem://f59c8f38958da3790dff02aae047ee5"
                        "e0b86c3a5599535f0d6da93e73dfce57d"
                    ): {
                        "schema_version": "policyos.normative_generation_disposition.v1",
                        "generation_binding": {
                            "compiled_run_ref": (
                                "sha256:65cefea4386572f6255089d2418cc43f9736c4122"
                                "7eb1352a351a80815b17458"
                            ),
                            "source_run_ref": (
                                "sha256:7339ca4100810a689fb1c0afbdbc441d557348f6d"
                                "b92842736e07099aef37f10"
                            ),
                            "node_ref": (
                                "design-problem://f59c8f38958da3790dff02aae047ee5"
                                "e0b86c3a5599535f0d6da93e73dfce57d"
                            ),
                        },
                        "compiled_membership_status": "not_established",
                        "case_id": ("worker_epoch_strangle_a05d9018aa114533b6af8df3cd71969a"),
                        "candidate_fronts": {
                            "decision": [],
                            "research": ["candidate_cgf_shadow"],
                            "quarantine": [],
                            "portfolio": [],
                        },
                        "dominance_status": "not_established",
                        "evidence": {
                            "frontier_ref": (
                                "sha256:8c31c36b85d97b882b117a8e3e505b27817de4a2e"
                                "4666a93ce84e3b1338e1988"
                            ),
                            "authorization_ref": (
                                "sha256:f772e62af8cb9b7fbb53b87902ae5d28efa9f7bee"
                                "167be3dbc94559848fa8329"
                            ),
                            "scope_ref": "fixture:explicit-value-scope",
                        },
                        "input_limitation": None,
                        "authorization_status": "authorized",
                        "ranked_recommendations": ["candidate_cgf_shadow"],
                        "decision_request": None,
                        "ranking_bundle_ref": (
                            "sha256:d1370363e62e579bcd7084baf56cf36a486b2ab04"
                            "1f422819f36661010819eae"
                        ),
                        "admitted_at": "2026-09-08T11:14:34.435182Z",
                        "trust_epoch": "explicit-test-deployment",
                        "authoritative_for": "value_schedule_for_ranking",
                        "may_not_use_for": [
                            "compiled_run_membership",
                            "pareto_dominance",
                            "empirical_value_authority",
                            "legal_competence",
                            "democratic_legitimacy",
                            "claim_evidence",
                            "publication_authority",
                        ],
                    }
                },
                "authorization_status": "authorized",
                "ranked_recommendations": ["candidate_cgf_shadow"],
                "strangle_receipt": {
                    "status": "strangled",
                    "default_entrypoint": ("ControlPlaneService.resolve_generation_value_choices"),
                    "predecessor": ("compiled_run_completion_without_normative_disposition"),
                    "default_flipped": True,
                    "compiled_run_ref": (
                        "sha256:65cefea4386572f6255089d2418cc43f9736c41227eb1352a351a80815b17458"
                    ),
                    "source_node_refs": [
                        (
                            "design-problem://f59c8f38958da3790dff02aae047ee5"
                            "e0b86c3a5599535f0d6da93e73dfce57d"
                        )
                    ],
                    "disposition_node_refs": [
                        (
                            "design-problem://f59c8f38958da3790dff02aae047ee5"
                            "e0b86c3a5599535f0d6da93e73dfce57d"
                        )
                    ],
                },
            },
            "normative_disposition_ref": (
                "sha256:5feaacea427178b78e4c1a56f748060d2bb27b728ac0062470d7655ffa087bb0"
            ),
            "phase": "natural_language_run",
            "promotion_refusal_reasons": ["epoch_validity_refused:policy_admission_missing"],
            "quality_scorecard": {"run_id": "R_9bfa9624a0a11eef"},
            "run_id": "R_9bfa9624a0a11eef",
            "state": "completed",
            "normative_head_ref": (
                "sha256:d7d43f5969fe8c96c135717ccc6772cab4a7ddfe36de6ceea2601a50830a6100"
            ),
            "normative_head_strangle_receipt": {
                "status": "strangled",
                "default_entrypoint": ("ControlPlaneService._current_normative_job_record"),
                "predecessor": "worker_only_normative_disposition",
                "default_flipped": True,
                "original_disposition_ref": (
                    "sha256:a697451cb06119ac48ac011bcc7e4e893d43458f1f89701bc823d7c83497ac6d"
                ),
                "current_disposition_ref": (
                    "sha256:5feaacea427178b78e4c1a56f748060d2bb27b728ac0062470d7655ffa087bb0"
                ),
            },
        },
    },
}


def _normative_evidence_transport_examples() -> dict[str, Any]:
    """Validate the captured fixture transport without granting production authority."""
    from polisyos.runtime.http.services.control.generation_cycle import (
        NormativeEvidenceSubmissionResponse,
    )

    NormativeEvidenceSubmissionResponse.model_validate_json(
        json.dumps(_NORMATIVE_EVIDENCE_FIXTURE_RESPONSE), strict=True
    )
    return {
        "positive_fixture_only_transport": {
            "summary": "Actual post-source fixture admission",
            "description": (
                "Documentation transport captured from the actual worker and later-signed "
                "HTTP intake using declared fixture sources, signers and trust; "
                "not production authority or a canonical denominator. "
                "Captured references and times describe that fixture run and must not "
                "be submitted as reusable authority evidence."
            ),
            "value": _NORMATIVE_EVIDENCE_FIXTURE_RESPONSE,
        }
    }


def _predictive_coverage_diagnostic_success_examples() -> dict[str, Any]:
    """Build the limited no-interval example through the canonical reader and projector."""
    from polisyos.core.artifacts import (
        ArtifactID,
        ArtifactManifest,
        ArtifactWriteOptions,
        CanonInfo,
        ManifestLifecycle,
        SchemaInfo,
        artifact_ref_for_manifest,
        expected_artifact_manifest_for_write,
        read_core_json_artifact,
    )
    from polisyos.core.canon import CanonSpec, content_hash, to_canonical_bytes
    from polisyos.core.contracts.runtime import PredictiveCoverageDiagnosticPreview
    from polisyos.runtime.http.services.artifact_inspector import (
        _predictive_coverage_preview,
    )

    fixture_canon_spec = CanonSpec(forbid_floats=False)
    fixture_payload = {
        "schema_version": "1.0",
        "metadata": {
            "estimand": "predictive_interval_coverage",
            "authority_scope": "predictive_only",
            "bridge_status": "bridge_pending",
        },
        "degraded_reasons": ["trust_screening:predictive_only_bridge_pending"],
        "degraded": True,
        "trust_eligible": False,
        "trust_score": None,
        "n_scenarios": 1,
        "scenarios": [
            {
                "scenario_id": "openapi-no-intervals",
                "requested_count": 1,
                "compared_count": 1,
                "missing_count": 0,
                "invalid_count": 0,
                "interval_requested_count": 1,
                "interval_available_count": 0,
                "interval_evaluated_count": 0,
                "interval_hit_count": 0,
                "interval_hit_rate": None,
                "coverage_probability": None,
                "nominal_confidence_level": 0.9,
                "interval_type": "prediction",
                "outcome_comparisons": [
                    {
                        "metric_name": "outcome",
                        "y_true": 1.0,
                        "ci_lower": None,
                        "ci_upper": None,
                        "within_ci": None,
                    }
                ],
            }
        ],
    }
    fixture_payload_bytes = to_canonical_bytes(fixture_payload, fixture_canon_spec)
    fixture_digest = content_hash(fixture_payload_bytes)
    fixture_manifest = expected_artifact_manifest_for_write(
        artifact_id=ArtifactID.from_sha256_hex(fixture_digest),
        data=fixture_payload_bytes,
        opts=ArtifactWriteOptions(
            kind="ir.backtest_report",
            media_type="application/json",
            schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
            canon=CanonInfo.from_spec(fixture_canon_spec),
        ),
        created_at=datetime(2026, 2, 11, 12, tzinfo=UTC),
    )
    fixture_ref = artifact_ref_for_manifest(fixture_manifest)
    fixture_manifest_bytes = ManifestLifecycle.to_bytes(fixture_manifest)

    class _InMemoryFixtureStore:
        """Expose only the content-bound fixture required by the canonical reader."""

        def _require_selected(self, selector: object, profile_sha256: str | None = None) -> None:
            if selector != fixture_ref or (
                profile_sha256 is not None and profile_sha256 != fixture_ref.manifest_profile_sha256
            ):
                raise FileNotFoundError("OpenAPI example fixture selection did not match")

        def get_bytes(self, selector: object) -> bytes:
            self._require_selected(selector)
            return fixture_payload_bytes

        def get_manifest(self, selector: object) -> ArtifactManifest:
            self._require_selected(selector)
            return fixture_manifest

        def get_raw_manifest_bytes(
            self,
            selector: object,
            *,
            manifest_profile_sha256: str | None = None,
        ) -> bytes:
            self._require_selected(selector, manifest_profile_sha256)
            return fixture_manifest_bytes

    profiled = read_core_json_artifact(_InMemoryFixtureStore(), fixture_ref)
    if profiled.status != "declared_bytes_conformant":
        raise ValueError("Controlled predictive fixture did not pass canonical byte reading")
    fixture_payload = profiled.value
    projected = _predictive_coverage_preview(
        fixture_payload,
        fixture_manifest,
        canon_read_status=profiled.status,
    )
    if projected is None:
        raise ValueError("Controlled predictive diagnostic fixture was not admitted")
    candidate = TypeAdapter(PredictiveCoverageDiagnosticPreview).validate_python(
        projected.model_dump(mode="json"),
        strict=True,
    )
    if (
        candidate.measurement_status != "not_measured"
        or candidate.reason_code != "no_evaluated_intervals"
        or len(candidate.scenarios) != 1
        or candidate.scenarios[0].interval_requested_count != 1
        or candidate.scenarios[0].interval_evaluated_count != 0
    ):
        raise ValueError("Controlled predictive fixture no longer emits its intended branch")
    return {
        "limited_not_measured_candidate": {
            "summary": "Limited diagnostic with a producer-reachable no-interval scenario",
            "description": (
                "Generated through the canonical Core byte/manifest reader and predictive-coverage "
                "projector from a controlled in-memory report fixture. Its digest is "
                "content-derived; "
                "the fixture is not stored production source, measurement, authority, issuer, "
                "publication, or currentness evidence."
            ),
            "value": candidate.model_dump(mode="json"),
        }
    }


def _lex_search_profile_success_examples() -> dict[str, Any]:
    """Build the typed no-selected-generation response example."""
    from polisyos.runtime.http.services.control.lex_search_profile import (
        LexSearchProfileRefusedResponse,
        LexSearchProfileResponse,
    )

    candidate = TypeAdapter(LexSearchProfileResponse).validate_python(
        {
            "meta": {
                "request_id": _REQUEST_ID_SAMPLE,
                "generated_at": datetime(2026, 2, 11, 12, tzinfo=UTC),
                "source_kinds": [],
            },
            "status": "refused",
            "output_dir": "example-legal-output",
            "refusal_code": "selected_generation_unavailable",
        },
        strict=True,
    )
    if not isinstance(candidate, LexSearchProfileRefusedResponse):
        raise ValueError("Lex profile example changed response arm")
    return {
        "selected_generation_unavailable": {
            "summary": "Typed refusal without a selected generation",
            "description": (
                "A refusal example only; it does not assert that an embedding generation "
                "is available or current."
            ),
            "value": candidate.model_dump(mode="json"),
        }
    }


@lru_cache(maxsize=1)
def _pre_admission_attempt_response_examples() -> dict[str, dict[str, Any]]:
    """Read a source-produced no-call refusal from a controlled in-memory owner."""
    import hashlib
    import sqlite3
    import threading
    import uuid
    from collections.abc import Iterator  # noqa: TC003 - contextmanager generator signature
    from contextlib import contextmanager
    from contextvars import ContextVar

    from polisyos.core.contracts import ControlPreAdmissionAttemptResponse
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

    class _OpenAPIInMemoryControlPlaneStore(ControlPlaneStore):
        """Reuse the owner schema and producers over one private memory connection."""

        def __init__(self) -> None:
            self.backend = "sqlite"
            self._sqlite_path = Path(":memory:")
            self._postgres_dsn = None
            self._lock = threading.RLock()
            self._human_decision_transaction = threading.local()
            self._job_execution_fence = ContextVar(
                "openapi_control_job_execution_fence", default=None
            )
            self._sqlite_timeout_seconds = 0.5
            self._connection = sqlite3.connect(":memory:", timeout=self._sqlite_timeout_seconds)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._ensure_sqlite_schema()

        @contextmanager
        def _sqlite_connection(self) -> Iterator[sqlite3.Connection]:
            yield self._connection

        def close(self) -> None:
            self._connection.close()

    tenant_id = "tenant-openapi-fixture"
    cell_id = "cell-openapi-fixture"
    actor_subject = "subject-openapi-fixture"
    run_id = "R_openapi_pre_admission_fixture"
    candidate_job_id = "job_openapi_pre_admission_fixture"
    effective_profile = "research"
    request_id = _REQUEST_ID_SAMPLE
    idempotency_key = "openapi-controlled-pre-admission-example"
    idempotency_digest = hashlib.sha256(idempotency_key.encode("ascii")).hexdigest()
    attempt_id = hashlib.sha256(
        "\0".join(
            (
                "control.nl_pre_admission.v1",
                "control.runs.nl",
                tenant_id,
                cell_id,
                actor_subject,
                idempotency_digest,
            )
        ).encode("utf-8")
    ).hexdigest()[:32]
    intent_binding = {
        "schema_version": "polisyos.runtime.control_pre_admission_intent.v1",
        "request_content_sha256": "sha256:"
        + hashlib.sha256(b"controlled OpenAPI fixture request; no provider call").hexdigest(),
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "actor_subject": actor_subject,
        "effective_execution_profile": effective_profile,
        "authorization_permission": "runs.launch",
        "authorization_resource_sha256": "sha256:"
        + hashlib.sha256(b"control.runs.nl fixture resource").hexdigest(),
    }
    fixed_time = datetime(2026, 2, 11, 12, tzinfo=UTC)
    store = _OpenAPIInMemoryControlPlaneStore()
    event_sequence = 0

    def stable_openapi_event_id() -> str:
        nonlocal event_sequence
        event_sequence += 1
        return uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"policyos-openapi-pre-admission:{attempt_id}:{event_sequence}",
        ).hex

    store._pre_admission_event_id_factory = stable_openapi_event_id
    try:
        store.start_pre_admission_attempt(
            attempt_id=attempt_id,
            request_id=request_id,
            run_id=run_id,
            candidate_job_id=candidate_job_id,
            effective_execution_profile=effective_profile,
            intent_binding=intent_binding,
            producer_run_binding=None,
            idempotency_key_sha256=idempotency_digest,
        )
        store.observe_pre_admission_attempt(
            attempt_id=attempt_id,
            event_type="refused",
            producer_event_observation="no_call",
            producer_no_call_reason="provider_preflight_not_started",
            failure_code="provider_preflight_not_started",
        )
        service = object.__new__(ControlPlaneService)
        service._control_store = store
        principal = RuntimePrincipal(
            subject=actor_subject,
            tenant_id=tenant_id,
            cell_id=cell_id,
            authenticated=True,
        )
        by_key = ControlPlaneService.get_pre_admission_attempt_status_by_idempotency_key(
            service,
            idempotency_key,
            request_id=request_id,
            principal=principal,
        )
        by_attempt = ControlPlaneService.get_pre_admission_attempt_status(
            service, attempt_id, request_id=request_id, principal=principal
        )

        def fixed_documentation_times(
            response: ControlPreAdmissionAttemptResponse,
        ) -> ControlPreAdmissionAttemptResponse:
            return response.model_copy(
                update={
                    "meta": response.meta.model_copy(update={"generated_at": fixed_time}),
                    "created_at": fixed_time,
                    "updated_at": fixed_time,
                    "history": [
                        event.model_copy(update={"observed_at": fixed_time})
                        for event in response.history
                    ],
                }
            )

        by_key_wire = json.dumps(
            fixed_documentation_times(by_key).model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
        )
        by_key = TypeAdapter(ControlPreAdmissionAttemptResponse).validate_json(
            by_key_wire, strict=True
        )
        by_attempt_wire = json.dumps(
            fixed_documentation_times(by_attempt).model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
        )
        by_attempt = TypeAdapter(ControlPreAdmissionAttemptResponse).validate_json(
            by_attempt_wire, strict=True
        )
        for candidate in (by_key, by_attempt):
            if (
                candidate.status != "refused"
                or candidate.producer_event_observation != "no_call"
                or candidate.producer_no_call_reason != "provider_preflight_not_started"
                or candidate.failure_code != candidate.producer_no_call_reason
                or candidate.producer_event_ids
                or candidate.owner_binding.purpose != "control.nl_pre_admission.v1"
                or candidate.owner_binding.scope_id != "control.runs.nl"
                or [event.event_type for event in candidate.history] != ["started", "refused"]
                or candidate.history[-1].producer_no_call_reason
                != candidate.producer_no_call_reason
            ):
                raise ValueError("Controlled pre-admission example changed owner refusal semantics")
        if by_key.model_dump(mode="json") != by_attempt.model_dump(mode="json"):
            raise ValueError("Pre-admission recovery routes disagree on owner readback")
        return {
            "by_idempotency_key": by_key.model_dump(mode="json"),
            "by_attempt_id": by_attempt.model_dump(mode="json"),
        }
    finally:
        store.close()


def _pre_admission_by_idempotency_success_examples() -> dict[str, Any]:
    """Return the producer-built actor-scoped recovery example."""
    return {
        "controlled_no_call_refusal": {
            "summary": "Actor-scoped attempt refused before provider preflight",
            "description": (
                "Projected from the durable pre-admission owner after its actual start and "
                "refused/no-call transitions in an in-memory controlled fixture. The actor, "
                "tenant, cell, run, request, timestamps, and deterministic event IDs are "
                "documentation fixtures; no provider call, production attempt, authorization "
                "grant, or reusable evidence is asserted."
            ),
            "value": _pre_admission_attempt_response_examples()["by_idempotency_key"],
        }
    }


def _pre_admission_by_attempt_id_success_examples() -> dict[str, Any]:
    """Return the producer-built actor-scoped history example."""
    return {
        "controlled_no_call_refusal": {
            "summary": "Actor-scoped history after provider preflight was not started",
            "description": (
                "Projected from the durable pre-admission owner after its actual start and "
                "refused/no-call transitions in an in-memory controlled fixture. The actor, "
                "tenant, cell, run, request, timestamps, and deterministic event IDs are "
                "documentation fixtures; no provider call, production attempt, authorization "
                "grant, or reusable evidence is asserted."
            ),
            "value": _pre_admission_attempt_response_examples()["by_attempt_id"],
        }
    }


def _predictive_calibration_success_examples() -> dict[str, Any]:
    """Build the typed limited abstention example without claiming stored calibration."""
    import hashlib

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.canon import CanonSpec, content_hash, to_canonical_bytes
    from polisyos.core.contracts.runtime import ApiMeta
    from polisyos.runtime.http.services.predictive_calibration import (
        _ASSOCIATION_KIND,
        _N4_OUTCOME_BINDING_LIMITATION_REF,
        PredictiveCalibrationAssociation,
        PredictiveCalibrationResponse,
        PredictiveCalibrationS10Summary,
    )
    from polisyos.runtime.quality.design_axes.outcome_prediction import build_forecast_support
    from polisyos.runtime.quality.generation_cycle import _s10_value_authority_boundary

    fixture_time = datetime(2026, 2, 11, 12, tzinfo=UTC)

    def fixture_ref(role: str, kind: str) -> ArtifactRef:
        digest = hashlib.sha256(f"openapi-predictive-calibration:{role}".encode()).hexdigest()
        return ArtifactRef(
            artifact_id=f"sha256:{digest}",
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256=(
                "sha256:" + hashlib.sha256(f"openapi-synthetic-profile:{role}".encode()).hexdigest()
            ),
        )

    source_limitation = "s10://calibration/fail-closed/backtest_source_not_established"
    authority = _s10_value_authority_boundary(predictive=True)
    support = build_forecast_support(
        support_id="n8.forecast-support.openapi-fixture",
        support_ref="s10://n8/openapi-fixture/forecast-support",
        case_id="openapi_predictive_calibration_fixture",
        source_design_record_ref="design://openapi-fixture",
        design_graph_ref="design-graph://openapi-fixture",
        prediction_context_ref="prediction-context://openapi-fixture",
        policy_context_ref="policy-context://openapi-fixture",
        candidate_design_ref="candidate://openapi-fixture",
        baseline_design_ref="baseline://openapi-fixture",
        alternative_design_refs=[],
        prediction_horizon_ref="horizon://openapi-fixture",
        target_outcome_refs=["outcome://openapi-fixture"],
        jurisdiction_scope_ref="jurisdiction://openapi-fixture",
        s5_forecast_support_ref="s5://openapi-fixture",
        s5_support_label="validated_local_dynamic_model",
        s5_base_origin="validated_local_model",
        s5_claim_scope="system_effect",
        s6_firewall_status_refs=["s6://openapi-fixture"],
        s6_limitation_refs=[_N4_OUTCOME_BINDING_LIMITATION_REF, source_limitation],
        s8_value_choice_provenance_ref="s8://openapi-fixture/value-choice",
        s8_value_tradeoff_disclosure_ref="s8://openapi-fixture/tradeoff",
        source_contract_ref="source-contract://openapi-fixture",
        method_validity_ref="method-validity://openapi-fixture",
        sensitivity_analysis_ref="sensitivity://openapi-fixture",
        dynamic_equilibrium_check_ref="equilibrium-check://openapi-fixture",
        outcome_distribution_refs=["distribution://openapi-fixture"],
        welfare_comparison_ref="welfare://openapi-fixture",
        forecast_authority_disposition_reason=(
            "Controlled OpenAPI example with an N4 binding limitation."
        ),
        method_family="foundry_forecast",
        limitation_refs=[_N4_OUTCOME_BINDING_LIMITATION_REF, source_limitation],
        authority_boundary=authority,
        may_not_use_for=authority["may_not_use_for"],
        rule_version_ref="policyos.layer2.s10.outcome_prediction.v1",
    )
    s10_summary = PredictiveCalibrationS10Summary(
        calibration_status="blocked",
        forecast_tier=support.forecast_tier,
        counterfactual_credibility="not_established",
        numerator=None,
        denominator=None,
        observed_pass_rate=None,
        outcome_binding_status="not_established",
        limitation_refs=tuple(support.limitation_refs),
        authority_boundary=support.authority_boundary.model_copy(deep=True),
        may_not_use_for=tuple(support.may_not_use_for),
    )
    association = PredictiveCalibrationAssociation(
        event_id="evt_predictive_calibration_openapi_fixture",
        intent_id="openapi-calibration-fixture",
        request_sha256=hashlib.sha256(b"openapi calibration fixture request").hexdigest(),
        run_id="R_openapi_predictive_calibration_fixture",
        control_run_id="control_openapi_predictive_calibration_fixture",
        job_id="job_openapi_predictive_calibration_fixture",
        tenant_id="tenant-openapi-fixture",
        cell_id="cell-openapi-fixture",
        run_manifest_ref=fixture_ref("run_manifest", "ir.run_manifest"),
        candidate_source_ref=fixture_ref(
            "candidate_source", "runtime.quality.n4_candidate_scenario_source"
        ),
        observed_source_ref=fixture_ref("observed_source", "fabric.data_snapshot"),
        model_spec_ref=fixture_ref("model_spec", "ir.model_spec"),
        policy_spec_ref=fixture_ref("policy_spec", "ir.policy_spec"),
        calibration_rule_ref=fixture_ref("calibration_rule", "ir.forecast_calibration_rule"),
        backtest_report_ref=fixture_ref("backtest_report", "ir.backtest_report"),
        empirical_evidence_ref=fixture_ref(
            "empirical_evidence", "runtime.empirical_calibration_evidence"
        ),
        uncertainty_bundle_ref=fixture_ref("uncertainty_bundle", "ir.uncertainty_bundle"),
        observed_numerator=None,
        observed_denominator=None,
        observed_hit_rate=None,
        owner_suitability="limited",
        s10=s10_summary,
        may_not_use_for=s10_summary.may_not_use_for or (),
        evidence_reason_codes=("backtest_source_not_established",),
        created_at=fixture_time,
    )
    association_bytes = to_canonical_bytes(
        association.model_dump(mode="json"), CanonSpec(forbid_floats=False)
    )
    association_ref = ArtifactRef(
        artifact_id=f"sha256:{content_hash(association_bytes)}",
        kind=_ASSOCIATION_KIND,
        media_type="application/json",
        manifest_profile_sha256=(
            "sha256:" + hashlib.sha256(b"openapi-synthetic-profile:association").hexdigest()
        ),
    )
    response = PredictiveCalibrationResponse(
        meta=ApiMeta(
            request_id=_REQUEST_ID_SAMPLE,
            generated_at=fixture_time,
            source_kinds=[],
        ),
        association_ref=association_ref,
        association=association,
    )
    response_wire = json.dumps(
        response.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
    )
    candidate = TypeAdapter(PredictiveCalibrationResponse).validate_json(response_wire, strict=True)
    if (
        candidate.association.assessment != "limited"
        or candidate.association.owner_suitability != "limited"
        or candidate.association.s10.calibration_status != "blocked"
        or candidate.association.s10.forecast_tier != "blocked"
        or any(
            value is not None
            for value in (
                candidate.association.observed_numerator,
                candidate.association.observed_denominator,
                candidate.association.observed_hit_rate,
                candidate.association.s10.numerator,
                candidate.association.s10.denominator,
                candidate.association.s10.observed_pass_rate,
                candidate.association.s10.calibration_record_ref,
            )
        )
        or source_limitation not in candidate.association.s10.limitation_refs
        or candidate.association.issuer_status != "not_established"
        or candidate.association.source_time_status != "not_established"
        or candidate.association.population_scope_status != "not_established"
        or candidate.association.counterfactual_credibility_status != "not_established"
        or candidate.association.authority_scope != "predictive_only"
        or candidate.association_ref.manifest_profile_sha256 is None
        or any(
            getattr(candidate.association, field).manifest_profile_sha256 is None
            for field in (
                "run_manifest_ref",
                "candidate_source_ref",
                "observed_source_ref",
                "model_spec_ref",
                "policy_spec_ref",
                "calibration_rule_ref",
                "backtest_report_ref",
                "empirical_evidence_ref",
                "uncertainty_bundle_ref",
            )
        )
    ):
        raise ValueError("Predictive calibration example exceeded its limited fixture scope")
    return {
        "controlled_insufficient_history_candidate": {
            "summary": "Limited candidate with unavailable observations",
            "description": (
                "Typed through the current predictive-calibration response and status owner. "
                "All artifact and manifest-profile identifiers are deterministic synthetic "
                "example handles matching the selected-reference wire shape; they establish "
                "no stored profile or provenance. The response is not persisted or reopenable "
                "evidence. "
                "Observed counts and hit rate are null because the empirical source is not "
                "established; S10 is blocked and carries the source limitation. "
                "This example asserts no POST outcome, currentness, issuer, "
                "population, causal, publication, or policy-selection authority."
            ),
            "value": candidate.model_dump(mode="json"),
        }
    }


_SUCCESS_SCHEMA_ANNOTATIONS = frozenset({"title", "description", "examples", "example"})
_INVALID_SCHEMA_REFERENCE = object


_URI_FRAGMENT_LITERAL_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~!$&'()*+,;=:@/?"
)
_URI_FRAGMENT_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def _is_valid_uri_fragment(fragment: str) -> bool:
    """Validate RFC 3986 fragment syntax: pchar, slash, or question mark."""
    index = 0
    while index < len(fragment):
        character = fragment[index]
        if character == "%":
            if (
                index + 2 >= len(fragment)
                or fragment[index + 1] not in _URI_FRAGMENT_HEX_DIGITS
                or fragment[index + 2] not in _URI_FRAGMENT_HEX_DIGITS
            ):
                return False
            index += 3
        elif character in _URI_FRAGMENT_LITERAL_CHARACTERS:
            index += 1
        else:
            return False
    return True


def _json_schema_pointer_tokens(reference: str) -> tuple[str, ...] | None:
    """Validate fragment syntax, then decode a local JSON Pointer."""
    if not reference.startswith("#"):
        return None
    fragment = reference[1:]
    if not _is_valid_uri_fragment(fragment):
        return None
    try:
        decoded = unquote(fragment, errors="strict")
    except UnicodeDecodeError:
        return None
    if not decoded:
        return ()
    if not decoded.startswith("/"):
        return None
    tokens: list[str] = []
    for raw in decoded[1:].split("/"):
        token: list[str] = []
        index = 0
        while index < len(raw):
            if raw[index] != "~":
                token.append(raw[index])
                index += 1
                continue
            if index + 1 >= len(raw) or raw[index + 1] not in {"0", "1"}:
                return None
            token.append("~" if raw[index + 1] == "0" else "/")
            index += 2
        tokens.append("".join(token))
    return tuple(tokens)


def _resolve_json_schema_pointer(document: object, reference: str) -> object | None:
    """Resolve a complete local JSON Pointer against its owning schema document."""
    tokens = _json_schema_pointer_tokens(reference)
    if tokens is None:
        return None
    target = document
    for part in tokens:
        if isinstance(target, dict) and part in target:
            target = target[part]
        elif (
            isinstance(target, list)
            and part
            and all("0" <= c <= "9" for c in part)
            and (part == "0" or not part.startswith("0"))
            and int(part) < len(target)
        ):
            target = target[int(part)]
        else:
            return None
    return target


def _success_json_schema_reference_projection(
    reference: str,
    *,
    document: object,
    active_refs: frozenset[tuple[str, ...]],
    memo: dict[tuple[str, ...], object],
) -> object:
    """Resolve and project a local schema target; unsupported references fail closed."""
    pointer = _json_schema_pointer_tokens(reference)
    if pointer is None:
        return _INVALID_SCHEMA_REFERENCE()
    target = _resolve_json_schema_pointer(document, reference)
    if target is None:
        return _INVALID_SCHEMA_REFERENCE()
    if pointer in active_refs:
        return {"$recursive_ref": True}
    if pointer not in memo:
        memo[pointer] = _success_json_schema_projection(
            target, document=document, active_refs=active_refs | {pointer}, memo=memo
        )
    return memo[pointer]


def _success_schema_explicitly_allows_null_default(schema: object) -> bool:
    """Recognize only supported schema shapes that explicitly admit null."""
    if not isinstance(schema, dict):
        return False
    supported_keywords = {
        "type",
        "const",
        "enum",
        "anyOf",
        "oneOf",
        "default",
        "title",
        "description",
        "examples",
        "example",
        "deprecated",
        "readOnly",
        "writeOnly",
        "$comment",
        "multipleOf",
        "maximum",
        "exclusiveMaximum",
        "minimum",
        "exclusiveMinimum",
        "maxLength",
        "minLength",
        "pattern",
        "format",
        "contentEncoding",
        "contentMediaType",
        "contentSchema",
        "maxItems",
        "minItems",
        "uniqueItems",
        "prefixItems",
        "items",
        "contains",
        "maxContains",
        "minContains",
        "maxProperties",
        "minProperties",
        "required",
        "properties",
        "patternProperties",
        "additionalProperties",
        "dependentRequired",
        "dependentSchemas",
        "propertyNames",
        "unevaluatedItems",
        "unevaluatedProperties",
    }
    if schema.keys() - supported_keywords:
        return False
    if "const" in schema and schema["const"] is not None:
        return False
    if "enum" in schema and (not isinstance(schema["enum"], list) or None not in schema["enum"]):
        return False

    schema_type = schema.get("type")
    positive_null = False
    if "type" in schema:
        if schema_type == "null":
            positive_null = True
        elif isinstance(schema_type, list):
            if "null" not in schema_type:
                return False
            positive_null = True
        elif isinstance(schema_type, str):
            return False
        else:
            return False
    if "const" in schema and schema["const"] is None:
        positive_null = True
    if "enum" in schema:
        positive_null = True

    if "anyOf" in schema:
        any_of = schema["anyOf"]
        if not isinstance(any_of, list) or not any(
            _success_schema_explicitly_allows_null_default(branch) for branch in any_of
        ):
            return False
        positive_null = True

    if "oneOf" in schema:
        one_of = schema["oneOf"]
        direct_nullability = {"type", "const", "enum"}
        if not isinstance(one_of, list) or any(
            not isinstance(branch, dict)
            or branch.keys() - supported_keywords
            or not direct_nullability.intersection(branch)
            or "anyOf" in branch
            or "oneOf" in branch
            for branch in one_of
        ):
            return False
        if sum(_success_schema_explicitly_allows_null_default(branch) for branch in one_of) != 1:
            return False
        positive_null = True

    return positive_null


def _success_json_schema_projection(
    schema: object,
    *,
    document: object,
    active_refs: frozenset[tuple[str, ...]] = frozenset(),
    memo: dict[tuple[str, ...], object] | None = None,
) -> object:
    """Resolve the supported local ref graph and normalize validation-bearing keywords."""
    if memo is None:
        memo = {}
    if isinstance(schema, list):
        return [
            _success_json_schema_projection(
                item, document=document, active_refs=active_refs, memo=memo
            )
            for item in schema
        ]
    if not isinstance(schema, dict):
        return schema
    if "$dynamicRef" in schema or "$recursiveRef" in schema:
        return _INVALID_SCHEMA_REFERENCE()
    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str):
            return _INVALID_SCHEMA_REFERENCE()
        resolved = _success_json_schema_reference_projection(
            reference, document=document, active_refs=active_refs, memo=memo
        )
        siblings = {
            key: value
            for key, value in schema.items()
            if key not in {"$ref", "$defs"} and key not in _SUCCESS_SCHEMA_ANNOTATIONS
        }
        if siblings:
            return {
                "allOf": [
                    resolved,
                    _success_json_schema_projection(
                        siblings, document=document, active_refs=active_refs, memo=memo
                    ),
                ]
            }
        return resolved
    projection: dict[str, object] = {}
    for key, value in schema.items():
        if (
            key == "default"
            and value is None
            and _success_schema_explicitly_allows_null_default(schema)
        ):
            continue
        if key == "$defs" or key in _SUCCESS_SCHEMA_ANNOTATIONS:
            continue
        if key == "$id" and isinstance(value, str) and value:
            projection[key] = _INVALID_SCHEMA_REFERENCE()
        elif key == "discriminator" and isinstance(value, dict):
            discriminator: dict[str, object] = {}
            for subkey, subvalue in value.items():
                if subkey == "mapping":
                    if not isinstance(subvalue, dict):
                        discriminator[subkey] = _INVALID_SCHEMA_REFERENCE()
                    else:
                        discriminator[subkey] = {
                            tag: {
                                "$schema_target": _success_json_schema_reference_projection(
                                    target,
                                    document=document,
                                    active_refs=active_refs,
                                    memo=memo,
                                )
                                if isinstance(target, str)
                                else _INVALID_SCHEMA_REFERENCE()
                            }
                            for tag, target in subvalue.items()
                        }
                else:
                    discriminator[subkey] = _success_json_schema_projection(
                        subvalue, document=document, active_refs=active_refs, memo=memo
                    )
            projection[key] = discriminator
        else:
            projection[key] = _success_json_schema_projection(
                value, document=document, active_refs=active_refs, memo=memo
            )
    return projection


_SUCCESS_EXAMPLE_SETS_BY_OPERATION: dict[
    str,
    dict[str, Any] | Callable[[], dict[str, Any]],
] = {
    "submit_run_normative_evidence": _normative_evidence_transport_examples,
    "search_capabilities": _CAPABILITY_DISCOVERY_SUCCESS_EXAMPLES,
    "search_data_catalog": _CAPABILITY_DISCOVERY_SUCCESS_EXAMPLES,
    "get_run_epoch_staleness": {
        "positive_fixture_only": {
            "summary": "Content-bound positive fixture",
            "value": _epoch_staleness_example(fixture_only=True),
        },
        "declared_production_absence": {
            "summary": "Production authority not appointed",
            "value": _epoch_staleness_example(fixture_only=False),
        },
    },
    "get_predictive_coverage_diagnostic": _predictive_coverage_diagnostic_success_examples,
    "get_lex_search_profile": _lex_search_profile_success_examples,
    "get_control_pre_admission_attempt_by_idempotency_key": (
        _pre_admission_by_idempotency_success_examples
    ),
    "get_control_pre_admission_attempt_status": _pre_admission_by_attempt_id_success_examples,
    "create_run_predictive_calibration": _predictive_calibration_success_examples,
    "get_run_predictive_calibration": _predictive_calibration_success_examples,
}


@lru_cache(maxsize=1)
def _success_example_response_models() -> dict[str, Any]:
    """Return response DTOs that govern model-dispatched success examples."""
    from polisyos.core.contracts import ControlPreAdmissionAttemptResponse
    from polisyos.core.contracts.control import ControlJobResponse
    from polisyos.core.contracts.runtime import (
        CompletedExAnteCandidateComparisonResponse,
        LineageBatchResponse,
        LineageExportResponse,
        LineageResponse,
        PredictiveCoverageDiagnosticPreview,
    )
    from polisyos.runtime.http.services.candidate_hte_packet_projection import (
        CandidateDecisionPacketHTEProjection,
    )
    from polisyos.runtime.http.services.control.lex_search_profile import (
        LexSearchProfileResponse,
    )
    from polisyos.runtime.http.services.predictive_calibration import (
        PredictiveCalibrationResponse,
    )
    from polisyos.runtime.http.services.registered_sql_service_contracts import (
        RegisteredSQLMaterializationResponse,
        RegisteredSQLRegistrationResponse,
        RegisteredSQLWithdrawalResponse,
    )

    return {
        "get_lineage": LineageResponse,
        "get_lineage_batch": LineageBatchResponse,
        "export_lineage_openlineage": LineageExportResponse,
        "export_lineage_prov": LineageExportResponse,
        "get_predictive_coverage_diagnostic": PredictiveCoverageDiagnosticPreview,
        "get_lex_search_profile": LexSearchProfileResponse,
        "get_run_method_metrics": MethodMetricProjectionResponse,
        "get_run_method_metric_comparison": CompletedExAnteCandidateComparisonResponse,
        "cancel_control_job": ControlJobResponse,
        "register_sql_source": RegisteredSQLRegistrationResponse,
        "admit_registered_sql_materialization": RegisteredSQLMaterializationResponse,
        "withdraw_registered_sql_materialization": RegisteredSQLWithdrawalResponse,
        "get_run_candidate_hte_packet": CandidateDecisionPacketHTEProjection,
        "get_control_pre_admission_attempt_by_idempotency_key": (
            ControlPreAdmissionAttemptResponse
        ),
        "get_control_pre_admission_attempt_status": ControlPreAdmissionAttemptResponse,
        "create_run_predictive_calibration": PredictiveCalibrationResponse,
        "get_run_predictive_calibration": PredictiveCalibrationResponse,
    }


@lru_cache(maxsize=1)
def _success_example_response_adapters() -> dict[str, TypeAdapter[Any]]:
    """Return strict JSON validators for model-dispatched success examples."""
    return {
        operation_id: TypeAdapter(response_model)
        for operation_id, response_model in _success_example_response_models().items()
    }


@lru_cache(maxsize=1)
def _confidence_ledger_risk_spend_example() -> dict[str, Any]:
    """Load and strictly admit the pinned historical DS17 documentation sample."""

    raw = (
        files("polisyos.runtime.http")
        .joinpath("_resources")
        .joinpath("confidence_ledger_risk_spend_openapi_example.json")
        .read_bytes()
    )
    if hashlib.sha256(raw).hexdigest() != _CONFIDENCE_LEDGER_RISK_SPEND_OPENAPI_EXAMPLE_SHA256:
        raise ValueError("DS17 OpenAPI example differs from its pinned SHA-256")

    admitted = TypeAdapter(ConfidenceLedgerRiskSpendPacket).validate_json(raw, strict=True)
    if not isinstance(admitted, AvailableConfidenceLedgerRiskSpendPacket):
        raise ValueError("DS17 historical OpenAPI example changed transport arm")

    sample_time = datetime(2026, 2, 11, 12, tzinfo=UTC)
    source = admitted.source
    validation = source.validation
    expected_artifact_hash = (
        "sha256:dd8f4be3afc8deefade824cb4bb4de0cce0d051fa262abb0c427c157ea770391"
    )
    expected_dependency_hash = (
        "sha256:4a0fd9f4e6ce949f538bbd8219afa144498fbc4bd8c1c0c2ab9ba12eea6c17aa"
    )
    expected_receipt_hash = (
        "sha256:74d4f2214adfcc1405f4ed46ef0d320c84be3f7217e8d9b756e8dee22af1e7ee"
    )
    if (
        source.relative_path
        != "architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json"
        or source.artifact_content_hash != expected_artifact_hash
        or source.declared_content_hash
        != "sha256:e971664fcdad74569735873c4a65f33922f2b4cd9e09d91fa39c1beba3cdb2a4"
        or validation.bound_artifact_content_hash != expected_artifact_hash
        or validation.bound_dependency_aggregate_identity != expected_dependency_hash
        or validation.bound_dependency_count != 1476
        or validation.worker_validation_receipt_hash != expected_receipt_hash
        or validation.status != "passed"
        or validation.issue_codes
        or admitted.source_dependency_hash != expected_dependency_hash
        or admitted.worker_validation_receipt_hash != expected_receipt_hash
        or admitted.worker_validation_receipt_ref != f"owner-validation:{expected_receipt_hash}"
        or admitted.replay_pins.artifact_content_hash != expected_artifact_hash
        or admitted.replay_pins.source_dependency_hash != expected_dependency_hash
        or admitted.as_of != sample_time
        or admitted.freshness.observed_at != sample_time
        or admitted.freshness.source_as_of != sample_time
        or admitted.freshness.basis != "filesystem_mtime"
        or admitted.freshness.state != "observed"
        or admitted.replay_pins.source_as_of != sample_time
    ):
        raise ValueError("DS17 historical provenance or example time pin changed")

    payload = admitted.payload
    measured_shape = (
        len(payload.refusal_instance_refs),
        len(payload.acquisition_instance_refs),
        len(payload.obligation_class_risk_spend),
        len(payload.instrument_definitions),
        len(payload.positive_register.entries),
        payload.total_spend.amount.fraction,
        payload.coverage_assessment.value,
        payload.status,
    )
    if measured_shape != (1, 2, 15, 13, 0, 0, "open_world_unresolved", "not_promoted"):
        raise ValueError("DS17 OpenAPI measured negative shape drifted")
    return admitted.model_dump(mode="json")


def _confidence_ledger_risk_spend_example_set() -> dict[str, Any]:
    """Return the historical packet as an explicitly non-current documentation example."""

    return {
        "default": {
            "summary": "Historical owner-validated documentation sample",
            "description": (
                "Pinned historical documentation sample from source commit "
                "be0bdb2bd2ac8d6a7dbb5eda6dbd25aac7516bf4. Its source artifact SHA-256 is "
                "dd8f4be3afc8deefade824cb4bb4de0cce0d051fa262abb0c427c157ea770391; "
                "the recorded dependency aggregate is "
                "sha256:4a0fd9f4e6ce949f538bbd8219afa144498fbc4bd8c1c0c2ab9ba12eea6c17aa "
                "and recorded worker receipt is "
                "sha256:74d4f2214adfcc1405f4ed46ef0d320c84be3f7217e8d9b756e8dee22af1e7ee. "
                "Example time: 2026-02-11T12:00:00Z. This is a documentation fixture, not a "
                "current availability or freshness claim; the live GET evaluates the owner "
                "source independently for each request."
            ),
            "value": _confidence_ledger_risk_spend_example(),
        }
    }


_SUCCESS_EXAMPLE_SETS_BY_OPERATION["get_confidence_ledger_risk_spend_projection"] = (
    _confidence_ledger_risk_spend_example_set
)


def _run_method_metric_projection_success_examples() -> dict[str, Any]:
    # Produce the owner-unavailable route fallback through its response DTO.
    encoded = json.dumps(
        {
            "meta": _META_CORE_RUN,
            "run_id": _RUN_ID_SAMPLE,
            "status": "verification_missing",
            "vector_ref": None,
            "observations": [],
            "limitations": ["current_method_metric_owner_unavailable"],
        },
        ensure_ascii=False,
        allow_nan=False,
    )
    response = MethodMetricProjectionResponse.model_validate_json(encoded, strict=True)
    return {
        "owner_unavailable": {
            "summary": "Current method-metric owner unavailable",
            "description": (
                "The route fallback when no current method-metric owner reader is available. "
                "No vector or observations are asserted."
            ),
            "value": response.model_dump(mode="json"),
        }
    }


_SUCCESS_EXAMPLE_SETS_BY_OPERATION["get_run_method_metrics"] = (
    _run_method_metric_projection_success_examples
)


def _synthetic_documentation_example(
    operation_id: str, payload: dict[str, Any], summary: str
) -> dict[str, Any]:
    """Validate a documentation-only response through its registered DTO."""
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    response = _success_example_response_adapters()[operation_id].validate_json(
        encoded, strict=True
    )
    return {
        "synthetic_documentation": {
            "summary": summary,
            "description": (
                "Synthetic documentation fixture only. Identifiers and hashes do not "
                "establish a real issuer, authorization, source, artifact, database "
                "currentness, candidate authority, or physical worker stop."
            ),
            "value": response.model_dump(mode="json"),
        }
    }


def _source_documentation_ref(kind: str, digit: str) -> dict[str, str]:
    """Create a selected-view placeholder without claiming that it resolves."""
    return {
        "artifact_id": "sha256:" + digit * 64,
        "kind": kind,
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "e" * 64,
    }


def _source_documentation_carrier() -> dict[str, Any]:
    """Describe an illustrative admission epoch, never an owner proof."""
    return {
        "tenant_id": "fixture-tenant",
        "cell_id": "fixture-cell",
        "source_incarnation_id": "fixture-source-1",
        "admission_scope_digest": "sha256:" + "f" * 64,
        "occurrence_id": "fixture-occurrence-1",
        "revision_digest": "sha256:" + "4" * 64,
        "admission_epoch": "fixture-epoch-1",
        "admission_event_ref": "sha256:" + "1" * 64,
        "snapshot_ref": _source_documentation_ref("fabric.data_snapshot", "c"),
        "use_contract_ref": _source_documentation_ref("fabric.registered_sql_use", "b"),
    }


def _source_documentation_receipt(operation: str) -> dict[str, Any]:
    """Construct a model-validated illustrative admit or withdrawal payload."""
    event_ref = "sha256:" + ("1" if operation == "admit" else "2") * 64
    return {
        "event_id": f"fixture-{operation}-event",
        "event_ref": event_ref,
        "operation": operation,
        "generation": 2 if operation == "admit" else 3,
        "committed_at": _TS_SAMPLE,
        "scope_head": event_ref,
        "carrier": _source_documentation_carrier(),
    }


def _registered_sql_registration_success_examples() -> dict[str, Any]:
    return _synthetic_documentation_example(
        "register_sql_source",
        {
            "registration": {
                "tenant_id": "fixture-tenant",
                "cell_id": "fixture-cell",
                "provider_id": "fixture-provider",
                "issuer_key": "documentation-fixture-not-an-issuer",
                "registration_key": "fixture-registration",
                "source_incarnation_id": "fixture-source-1",
                "effective_view_contract_ref": _source_documentation_ref(
                    "fabric.registered_sql_view", "a"
                ),
                "use_contract_ref": _source_documentation_ref("fabric.registered_sql_use", "b"),
                "admission_scope_digest": "sha256:" + "f" * 64,
                "event_id": "fixture-registration-event",
                "event_ref": "sha256:" + "0" * 64,
                "generation": 1,
                "committed_at": _TS_SAMPLE,
            }
        },
        "Synthetic source registration response",
    )


def _registered_sql_materialization_success_examples() -> dict[str, Any]:
    return _synthetic_documentation_example(
        "admit_registered_sql_materialization",
        {
            "status": "committed",
            "receipt": _source_documentation_receipt("admit"),
            "binding_ref": _source_documentation_ref(
                "fabric.registered_sql_admission_binding", "d"
            ),
            "current_use": "not_checked",
            "external_database_currentness": "not_established",
        },
        "Synthetic materialization response with current use not checked",
    )


def _registered_sql_withdrawal_success_examples() -> dict[str, Any]:
    return _synthetic_documentation_example(
        "withdraw_registered_sql_materialization",
        {"receipt": _source_documentation_receipt("withdraw")},
        "Synthetic source withdrawal response",
    )


def _cancel_control_job_success_examples() -> dict[str, Any]:
    return _synthetic_documentation_example(
        "cancel_control_job",
        {
            "meta": _META_NO_SOURCE,
            "job_id": "fixture-job-1",
            "kind": "workflow_run",
            "state": "cancelled",
            "effective_execution_profile": "dev",
            "cancellation_disposition": "publication_fenced",
            "physical_stop_status": "not_established",
        },
        "Synthetic cancellation response with physical stop not established",
    )


def _run_method_metric_comparison_success_examples() -> dict[str, Any]:
    return _synthetic_documentation_example(
        "get_run_method_metric_comparison",
        {
            "meta": _META_CORE_RUN,
            "run_id": _RUN_ID_SAMPLE,
            "candidate_comparison": {
                "status": "verification_missing",
                "limitations": ["current_candidate_comparison_owner_unavailable"],
            },
        },
        "Synthetic candidate comparison with verification missing",
    )


_SUCCESS_EXAMPLE_SETS_BY_OPERATION.update(
    {
        "cancel_control_job": _cancel_control_job_success_examples,
        "register_sql_source": _registered_sql_registration_success_examples,
        "admit_registered_sql_materialization": _registered_sql_materialization_success_examples,
        "withdraw_registered_sql_materialization": _registered_sql_withdrawal_success_examples,
        "get_run_method_metric_comparison": _run_method_metric_comparison_success_examples,
    }
)


def _run_candidate_hte_packet_success_examples() -> dict[str, Any]:
    """Build a controlled absence fixture through the packet projection owner."""
    from polisyos.runtime.http.services.candidate_hte_packet_projection import (
        CandidateDecisionPacketHTEProjection,
        project_candidate_hte_packet,
    )

    packet_ref = core_artifacts.ArtifactRef(
        artifact_id=_ARTIFACT_ID_SAMPLE,
        kind="scientist.decision_packet",
        media_type="application/json",
        manifest_profile_sha256=_SHA_LINEAGE,
    )
    packet_payload: dict[str, Any] = {
        "schema_version": "3.4",
        "hte": None,
        "decision_validity_envelope": {
            "data_basis": {
                "summary": {
                    "completed_hte_source_status": "verification_missing",
                    "completed_hte_request_status": "requested",
                    "completed_hte_requested_source_run_id": _RUN_ID_SAMPLE,
                    "completed_hte_authority_purpose": "candidate_method_evidence",
                    "completed_hte_publication_authorization": "not_established",
                    "completed_hte_currentness_status": "not_established",
                    "completed_hte_limitations": ["completed_hte_source_not_established"],
                }
            }
        },
    }
    projection = project_candidate_hte_packet(
        packet_payload=packet_payload,
        packet_run_id=_RUN_ID_SAMPLE,
        packet_ref=packet_ref,
        source_run_id_selector=_RUN_ID_SAMPLE,
        fresh_source=None,
        reader_at=datetime.fromisoformat(_TS_SAMPLE.replace("Z", "+00:00")),
    )
    response = CandidateDecisionPacketHTEProjection.model_validate_json(
        json.dumps(projection.model_dump(mode="json"), ensure_ascii=False, allow_nan=False),
        strict=True,
    )
    return {
        "controlled_absence_fixture": {
            "summary": "Controlled candidate-source absence fixture",
            "description": (
                "Documentation-only fixture for a DecisionPacket whose completed HTE source "
                "could not be established. It contains no source candidate, does not establish "
                "live source currentness, and grants no publication authorization. The live "
                "route resolves the selected packet and owner source on each request."
            ),
            "value": response.model_dump(mode="json"),
        }
    }


_SUCCESS_EXAMPLE_SETS_BY_OPERATION["get_run_candidate_hte_packet"] = (
    _run_candidate_hte_packet_success_examples
)


_SUCCESS_EXAMPLES_BY_OPERATION: dict[
    str,
    dict[str, Any] | Callable[[], dict[str, Any]],
] = {
    "admit_epoch_validity_batch": _epoch_validity_batch_example(),
    "list_run_acquisition_routes": {
        "run_id": "run-ds15",
        "routes": [],
    },
    "get_run_acquisition_route": {
        "schema_version": "AcquisitionRouteProjection@1.1",
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-ds15",
        "route_id": _ARTIFACT_ID_SAMPLE,
        "route_projection_hash": _ARTIFACT_ID_SAMPLE,
        "planner_report_hash": "sha256:" + "b" * 64,
        "planner_record_id": "acquisition-data-gap",
        "recommended_strategy": "registered_query",
        "cost_basis": {"record_content_hash": "sha256:" + "c" * 64},
        "replay_pins": {
            "source_job_id": "job-natural-language",
            "compiled_ref": "sha256:" + "d" * 64,
            "compiled_content_hash": "sha256:" + "e" * 64,
            "terminal_event_id": "evt-natural-language-terminal",
            "design_problem_ref": "sha256:" + "f" * 64,
            "cost_basis_hash": "sha256:" + "c" * 64,
        },
        "route_status": "costed_actionable",
        "authority_capability": "producer_missing",
        "execution_capability": "producer_missing",
        "qualification_status": "pending_epoch_activation",
        "qualification_predicate": "not_established",
        "qualification_reason": "policy_admission_missing",
        "world_growth": "not_established",
        "admitted_observation_delta": None,
        "authority_badge": "behavioral_fixture_not_production",
        "external_nonclosures": [
            "fresh_positive_production_route:absent/unallocated",
            "current_mandate_owner:producer_missing",
            "deterministic_admission_bundle:producer_missing",
            "non_fixture_n13b_owner_port:bridge_missing",
        ],
    },
    "request_run_acquisition_decision": {
        "run_id": "run-ds15",
        "route_id": _ARTIFACT_ID_SAMPLE,
        "authority_decision_ref": "sha256:" + "1" * 64,
        "outcome": "decision_required",
        "human_decision_request": {"request_ref": "pdc://human-decision/ds15"},
        "world_growth": "not_established",
    },
    "execute_run_acquisition_route": {
        "run_id": "run-ds15",
        "route_id": _ARTIFACT_ID_SAMPLE,
        "job_id": "acquisition-deferred-job",
        "authority_decision_ref": "sha256:" + "1" * 64,
        "status": "accepted",
        "receipt_phase": "requested",
        "world_growth": "not_established",
    },
    "create_run_human_decision": _HUMAN_DECISION_CREATE_SAMPLE,
    "get_run_authority_values": {
        "run_id": "run-2026-08-17-001",
        "inventory_version": "ds16-c05.1",
        "retirement_commit": "bc1d01001",
        "values": [
            {
                "value_id": "readiness.composite_verdict",
                "surface": "readiness",
                "state": "refused",
                "refusal_code": "no_runtime_composition_rule",
                "reason": ("No governed artifact defines how a readiness verdict is composed."),
                "retired_from": (
                    "apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts"
                ),
                "owner_surface": None,
            },
            {
                "value_id": "readiness.lens_projection",
                "surface": "readiness",
                "state": "refused",
                "refusal_code": "owned_by_another_surface",
                "reason": (
                    "Stakeholder-lens projection is audience mapping, owned by the "
                    "DS0/DS3 audience grammar."
                ),
                "retired_from": (
                    "apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts"
                ),
                "owner_surface": "atlas audience mapping (DS0/DS3)",
            },
        ],
    },
    "health": {"status": "ok"},
    "ready": {"status": "ready"},
    "runtime_api_health": {
        "status": "ok",
        "service": "runtime_api_v1",
        "ts": _TS_SAMPLE,
    },
    "list_governed_projections": {
        "schema_version": "policyos.runtime.governed_projection_catalog.v1",
        "projections": [
            {
                "projection_id": "engine-census",
                "expected_source_path": (
                    "architecture/policy_design_case/layer3_gy_task0_audit/"
                    "layer3_gy_engine_census.json"
                ),
                "source_policy": "required",
                "intended_audience": "EXPERT",
                "authoritative_for": ["engine_census_summary", "critical_findings"],
                "may_not_use_for": [
                    "public_claim",
                    "publication_authority",
                    "audience_authorization",
                    "row_level_engine_export",
                ],
                "expected_source_schema_version": (
                    "policyos.policy_design_case.layer3_gy_engine_census.v1"
                ),
                "expected_source_rule_version": ("policyos.layer3.gy.engine_reality_census.v1"),
                "owner_validator_id": (
                    "tools.quality.validation.check_layer3_gy_engine_census:validate"
                ),
                "owner_validator_version": (
                    "policyos.policy_design_case.layer3_gy_engine_census.v1"
                ),
                "stable_address": "/api/v1/exports/governed-projections/engine-census",
            }
        ],
    },
    "get_governed_projection": {
        "packet_schema_version": "policyos.runtime.governed_projection_packet.v1",
        "export_replay_contract": "policyos.runtime.export_replay_binding.v1",
        "projection_id": "engine-census",
        "projection_rule_version": "policyos.runtime.governed_projection.v1",
        "intended_audience": "EXPERT",
        "authoritative_for": ["engine_census_summary", "critical_findings"],
        "may_not_use_for": [
            "public_claim",
            "publication_authority",
            "audience_authorization",
            "row_level_engine_export",
        ],
        "source_schema_version": ("policyos.policy_design_case.layer3_gy_engine_census.v1"),
        "source_rule_version": "policyos.layer3.gy.engine_reality_census.v1",
        "as_of": _TS_SAMPLE,
        "freshness": {
            "state": "observed",
            "basis": "filesystem_mtime",
            "observed_at": _TS_SAMPLE,
            "source_as_of": _TS_SAMPLE,
        },
        "stable_address": "/api/v1/exports/governed-projections/engine-census",
        "availability": "available",
        "source": {
            "relative_path": (
                "architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_engine_census.json"
            ),
            "artifact_content_hash": _SHA_DATA,
            "declared_content_hash": None,
            "validation": {
                "validator_id": ("tools.quality.validation.check_layer3_gy_engine_census:validate"),
                "validator_version": ("policyos.policy_design_case.layer3_gy_engine_census.v1"),
                "status": "passed",
                "bound_artifact_content_hash": _SHA_DATA,
                "bound_dependency_aggregate_identity": _SHA_BINDINGS,
                "bound_dependency_count": 1,
                "semantic_projection_hash": _SHA_PLAN,
                "semantic_projection_hash_rule_version": ("polisyos.pdc.gy_content_hash.v1"),
                "issue_codes": [],
            },
            "related_artifact_bindings": [],
        },
        "source_dependency_hash": _SHA_BINDINGS,
        "projection_hash": _SHA_PLAN,
        "replay_address": (
            "/api/v1/exports/governed-projections/engine-census?"
            f"artifact_content_hash={_SHA_DATA}&projection_hash={_SHA_PLAN}&"
            f"source_dependency_hash={_SHA_BINDINGS}&source_as_of={_TS_SAMPLE}"
        ),
        "payload": {
            "row_count": 1,
            "execution_status_vocabulary": {"implemented": 1},
            "critical_findings": [],
            "subcensus_summary": {},
            "gap_taxonomy_extensions": {},
            "verb_gap_consistency": {},
            "evidence_reproducibility": {},
            "discipline": "owner_validated",
            "scope": "engine_census_summary",
        },
        "absence_reason": None,
    },
    "get_case_inspection": _RUN_PAPER_TYPED_UNAVAILABLE_SAMPLE,
    "get_run_human_decision_gate": {
        "status": "producer_missing",
        "reasons": [
            {
                "code": "DS9-DECISION-PRODUCER-MISSING",
                "message": "The deployment human-decision producer is unavailable.",
                "status": "producer_missing",
            }
        ],
        "reason_codes": ["DS9-DECISION-PRODUCER-MISSING"],
        "source_kind": "agent_action_authority",
        "source_ref": None,
        "tenant_id": "tenant-openapi-sample",
        "run_id": _RUN_ID_SAMPLE,
        "decision_request_ref": None,
        "decision_request_digest": None,
        "governed_action_key": None,
        "decision_request": None,
        "mandate": None,
        "exposure": {
            "exposure_session_ref": None,
            "required_artifact_digests": [],
            "completed_artifact_digests": [],
        },
        "contestability": None,
        "continuation": None,
        "submission": None,
        "resolved_at": _TS_SAMPLE,
        "verifier_epoch": "producer-missing",
        "operational_authority": False,
    },
    "get_run_human_decision_record": _HUMAN_DECISION_RECORD_SAMPLE,
    "get_run_human_decision_review_effectiveness": {
        "schema_version": "policyos.runtime.human_decision_review_effectiveness.v1",
        "run_id": _RUN_ID_SAMPLE,
        "coverage_status": "incomplete",
        "trail_path_exists": False,
        "nonblank_line_count": 0,
        "parsed_object_count": 0,
        "malformed_json_line_count": 0,
        "nonobject_line_count": 0,
        "audit_read_error_count": 0,
        "authorization_allow_count": 0,
        "candidate_human_decision_count": 0,
        "completed_human_decision_count": 0,
        "exact_join_count": 0,
        "invalid_authorization_event_count": 0,
        "invalid_record_event_count": 0,
        "tenant_scope_unknown_record_event_count": 0,
        "unmatched_authorization_count": 0,
        "unmatched_record_event_count": 0,
        "duplicate_authorization_request_count": 0,
        "duplicate_record_request_count": 0,
        "duplicate_record_event_count": 0,
        "retained_or_missing_record_count": 0,
        "review_count": 0,
        "approval_count": 0,
        "override_count": 0,
        "blocking_count": 0,
        "dissent_count": 0,
        "reviewer_independence_rate": None,
        "separation_of_duty_attestation_rate": None,
        "review_time_not_established_count": 0,
        "threshold_status": "warn",
        "advisory_signal_codes": ["human_decision_review_coverage_incomplete"],
    },
    "get_depth_n_cycle_board_projection": _CYCLE_BOARD_COMPOSED_ABSENCE_SAMPLE,
    "get_run_paper": _RUN_PAPER_TYPED_UNAVAILABLE_SAMPLE,
    "get_runtime_channel_registry": {
        "schema_version": "policyos.runtime.channel_registry.v1",
        "channels": [
            {
                "registry_id": "runs-list-live",
                "path_template": "/api/v1/runs/live",
                "transport": "sse",
                "channels": [],
                "message_contract": "policyos.runtime.runs_channel_data_event.v2",
                "producer_contract_ref": (
                    "polisyos.runtime.http.services.channel_contracts:RunsChannelDataEvent"
                ),
                "auth_class": "runtime_tenant_access+stream_rate_limit",
                "consumers": ["apps/runtime-dashboard:RunsLiveProvider"],
                "owner": "polisyos.runtime.http.routes.runs",
                "capability_state": "verification_missing",
                "include_in_schema": False,
                "status": "active",
            },
            {
                "registry_id": "run-detail-live",
                "path_template": "/api/v1/runs/{run_id}/live",
                "transport": "sse",
                "channels": [],
                "message_contract": "policyos.runtime.runs_channel_data_event.v2",
                "producer_contract_ref": (
                    "polisyos.runtime.http.services.channel_contracts:RunsChannelDataEvent"
                ),
                "auth_class": "runtime_run_tenant_access+stream_rate_limit",
                "consumers": ["apps/runtime-dashboard:useRunLiveUpdates"],
                "owner": "polisyos.runtime.http.routes.runs",
                "capability_state": "verification_missing",
                "include_in_schema": False,
                "status": "active",
            },
            {
                "registry_id": "review-live",
                "path_template": "/api/v1/review/live",
                "transport": "websocket",
                "channels": ["review.cursor", "review.lock", "review.presence"],
                "message_contract": ("policyos.runtime.review_collaboration_envelope.v1"),
                "producer_contract_ref": (
                    "polisyos.runtime.http.services.channel_contracts:ReviewSnapshot"
                ),
                "auth_class": ("runtime_review_socket_auth+tenant_opa_action+stream_rate_limit"),
                "consumers": ["apps/runtime-dashboard:useReviewCollaborationSurface"],
                "owner": "polisyos.runtime.http.routes.review",
                "capability_state": "verification_missing",
                "include_in_schema": False,
                "status": "active",
            },
        ],
    },
    "get_auth_me": {
        "meta": _META_NO_SOURCE,
        "user_id": "fixture-analyst",
        "display_name": "Fixture Analyst",
        "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "principal_type": "user",
        "cell_id": "cell-a",
        "roles": ["analyst"],
        "permissions": _ANALYST_PERMISSION_EXAMPLE,
        "mfa_verified": True,
        "feature_overrides": {
            "enableReviewCollaboration": False,
        },
    },
    "list_runs": {
        "meta": _META_CORE_RUN,
        "page": {
            "limit": 50,
            "cursor": None,
            "next_cursor": None,
            "count": 1,
            "total": 1,
        },
        "runs": [
            {
                "run_id": _RUN_ID_SAMPLE,
                "source_kind": "core_run",
                "status": "completed",
                "run_terminality": "terminal",
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
    "create_run_production_approval": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "decision": "blocked",
        "packet": {
            "schema_version": "policyos.production_approval_packet.v1",
            "generated_at": _TS_SAMPLE,
            "run_id": _RUN_ID_SAMPLE,
            "job_id": "job_ctrl_abcdef01",
            "canary_kind": "governed",
            "decision": "blocked",
            "eligibility": {
                "eligible": False,
                "execution_completed": True,
                "quality_passed": False,
                "blocking_failure_count": 1,
                "performance_status": "pass",
                "performance_blocking": False,
                "conflict_status": "pass",
                "conflict_blocking": False,
                "reasons": ["quality_not_passing", "blocking_quality_failures"],
            },
            "scorecard_ref": _ARTIFACT_ID_SAMPLE,
            "scorecard_digest": "sha256:" + "e" * 64,
            "scorecard_generated_at": _TS_SAMPLE,
            "evidence_refs": {
                "quality_scorecard": _ARTIFACT_ID_SAMPLE,
                "readiness_aggregator": "docs/archive/reports/readiness_aggregator.json",
                "resilience_matrix": "docs/archive/reports/resilience_matrix.json",
            },
            "override": None,
        },
        "approval_packet_ref": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "runtime.production_approval_packet",
            "media_type": "application/json",
        },
        "evidence_bundle_packet_path": (
            ".polisyos/canary_evidence/sample/production_approval_packet.json"
        ),
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
                        "prov": "/api/v1/lineage/artifact:" + _ARTIFACT_ID_SAMPLE + "/export/prov",
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
        "lineage_resolutions": [
            {
                "requested_lineage_id": "artifact:" + _ARTIFACT_ID_SAMPLE,
                "resolved_lineage_id": "artifact:" + _ARTIFACT_ID_SAMPLE,
            }
        ],
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
                {
                    "namespace": "polisyos.lineage",
                    "name": "artifact:" + _ARTIFACT_ID_SAMPLE,
                }
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
                "plan_hash": _SHA_PLAN,
                "registry_hash": _SHA_REGISTRY,
                "method_catalog_hash": _SHA_METHOD,
                "data_snapshot_hash": _SHA_DATA,
                "input_bindings_hash": _SHA_BINDINGS,
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
    "get_node_simulation_result_candidate": {
        "meta": _META_CORE_RUN,
        "debug": {
            "run_id": _RUN_ID_SAMPLE,
            "node_alias": "run_simulation",
            "node_id": "scientist.node_run_simulation@1.0.0",
            "artifact_ref": {
                "artifact_id": _ARTIFACT_ID_SAMPLE,
                "kind": "foundry.simulation_result",
                "media_type": "application/json",
            },
            "simulation_result": {
                "schema_version": "1.3",
                "exec_plan_ref": {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "kind": "foundry.exec_plan",
                    "media_type": "application/json",
                },
                "metrics_ref": {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "kind": "foundry.metrics",
                    "media_type": "application/json",
                },
                "notes": ["candidate reference only"],
            },
            "projection_class": "candidate_reference_only",
            "authority_status": "non_authority",
            "integrity_status": "verified",
            "notes": [
                "candidate_reference_only",
                "not_an_authority_envelope",
                "generic_artifact_authority_routes_remain_blocked",
            ],
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
                "decision_lineage_key": _SHA_LINEAGE,
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
                    "data": {
                        "changed": False,
                        "refs": {},
                        "summary": {},
                        "details": {},
                    },
                    "evidence": {
                        "changed": False,
                        "refs": {},
                        "summary": {},
                        "details": {},
                    },
                    "model": {
                        "changed": False,
                        "refs": {},
                        "summary": {},
                        "details": {},
                    },
                    "governance": {
                        "changed": False,
                        "refs": {},
                        "summary": {},
                        "details": {},
                    },
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
                    "data": {
                        "changed": False,
                        "refs": {},
                        "summary": {},
                        "details": {},
                    },
                    "evidence": {
                        "changed": False,
                        "refs": {},
                        "summary": {},
                        "details": {},
                    },
                    "model": {
                        "changed": False,
                        "refs": {},
                        "summary": {},
                        "details": {},
                    },
                    "governance": {
                        "changed": False,
                        "refs": {},
                        "summary": {},
                        "details": {},
                    },
                    "outcome": {
                        "changed": False,
                        "refs": {},
                        "summary": {},
                        "details": {},
                    },
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
            "manifest_profile_sha256": "sha256:" + "b" * 64,
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
                "manifest_profile_sha256": "sha256:" + "b" * 64,
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
            "manifest_profile_sha256": "sha256:" + "b" * 64,
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
            "root_artifact_refs": [
                {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "kind": "scientist.workflow_report",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:" + "b" * 64,
                }
            ],
            "total_nodes": 1,
            "total_edges": 0,
            "total_size_bytes": 1024,
            "is_complete": True,
            "missing_artifact_ids": [],
            "corrupted_artifact_ids": [],
            "nodes": [
                {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "manifest_profile_sha256": "sha256:" + "b" * 64,
                    "role": "root",
                    "kind": "scientist.workflow_report",
                    "media_type": "application/json",
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
            "manifest_profile_sha256": "sha256:" + "b" * 64,
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
            "Agent circuit was queued in single model: qwen-policy-runtime."
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
        "runtime_api_version": "1.1.0",
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
            "execution_policy": {
                "auto_materialization": True,
                "multimodel_nl": True,
                "producer_ref": "runtime/http/services/_control_contracts.py",
                "required_preflight": True,
            },
        },
        "workspaces": [],
        "features": [],
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
        "content": '<article data-policyos-document="doc_fixture_001"></article>',
        "metadata": {
            "watermark": _BUREAUCRATIC_DOCUMENT_SAMPLE["watermark"],
            "template_version": "ua.kmu.postanova.v1",
        },
    },
}


def _first_success_response(
    responses: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    """Return the lowest declared 2xx response without assuming every write is 200."""
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for status_code, response in responses.items():
        if (
            isinstance(status_code, str)
            and status_code.isdigit()
            and 200 <= int(status_code) < 300
            and isinstance(response, dict)
        ):
            candidates.append((int(status_code), status_code, response))
    if not candidates:
        return None
    _numeric, status_code, response = min(candidates, key=lambda item: item[0])
    return status_code, response


def _schema_references_runtime_api_problem(schema: object) -> bool:
    """Return whether a response schema directly uses the runtime problem model."""
    if not isinstance(schema, dict):
        return False
    if schema.get("$ref") == _RUNTIME_PROBLEM_SCHEMA_REF:
        return True
    for keyword in ("allOf", "anyOf", "oneOf"):
        branches = schema.get(keyword)
        if isinstance(branches, list) and any(
            _schema_references_runtime_api_problem(branch) for branch in branches
        ):
            return True
    return False


def augment_runtime_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    """Augment runtime openapi helper."""
    mutated = deepcopy(schema)
    components = mutated.setdefault("components", {})
    component_schemas = components.setdefault("schemas", {})
    for alias, owner in _SCHEMA_COMPATIBILITY_ALIASES.items():
        if owner not in component_schemas:
            raise ValueError(f"OpenAPI compatibility alias owner is missing: {owner}")
        component_schemas[alias] = {"$ref": f"#/components/schemas/{owner}"}
    runtime_problem_schema = RuntimeApiProblem.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    runtime_problem_defs = runtime_problem_schema.pop("$defs", {})
    if isinstance(runtime_problem_defs, dict):
        for name, definition in runtime_problem_defs.items():
            if not isinstance(name, str) or not isinstance(definition, dict):
                continue
            existing = component_schemas.get(name)
            if existing is not None and existing != definition:
                raise ValueError(
                    f"RuntimeApiProblem nested schema conflicts with component: {name}"
                )
            component_schemas[name] = definition
    component_schemas["RuntimeApiProblem"] = runtime_problem_schema
    human_decision_record_schema = HumanDecisionRecord.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    human_decision_record_defs = human_decision_record_schema.pop("$defs", {})
    if isinstance(human_decision_record_defs, dict):
        for name, definition in human_decision_record_defs.items():
            if isinstance(name, str) and isinstance(definition, dict):
                component_schemas.setdefault(name, definition)
    record_properties = human_decision_record_schema.get("properties")
    if isinstance(record_properties, dict):
        schema_version = record_properties.get("schema_version")
        if isinstance(schema_version, dict):
            schema_version["enum"] = [
                LAYER2_S7_DELEGATION_SCHEMA_VERSION,
                HUMAN_DECISION_RECORD_V2,
            ]
    record_required = human_decision_record_schema.setdefault("required", [])
    if isinstance(record_required, list) and "schema_version" not in record_required:
        record_required.append("schema_version")
    component_schemas["HumanDecisionRecord"] = human_decision_record_schema

    for path, _, operation in iter_openapi_operations(mutated):
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
            payload = content.setdefault(_RUNTIME_PROBLEM_MEDIA_TYPE, {})
            if not isinstance(payload, dict):
                continue
            payload.setdefault("schema", {"$ref": _RUNTIME_PROBLEM_SCHEMA_REF})
            if "example" not in payload and not payload.get("examples"):
                payload["examples"] = {
                    "default": {
                        "summary": descriptor["description"],
                        "value": runtime_problem_example(
                            status_code=int(status_code),
                            code=descriptor["code"],
                            path=path,
                            request_id=_REQUEST_ID_SAMPLE,
                        ),
                    }
                }

        for status_code, response_payload in responses.items():
            if str(status_code) in _DEFAULT_PROBLEM_RESPONSES:
                continue
            if not isinstance(response_payload, dict):
                continue
            response_content = response_payload.get("content")
            if not isinstance(response_content, dict):
                continue
            problem_payload = response_content.get(_RUNTIME_PROBLEM_MEDIA_TYPE)
            if (
                not isinstance(problem_payload, dict)
                or problem_payload.get("schema") != {"$ref": _RUNTIME_PROBLEM_SCHEMA_REF}
                or "example" in problem_payload
                or problem_payload.get("examples")
            ):
                continue
            try:
                numeric_status = int(status_code)
            except (TypeError, ValueError):
                continue
            code = "conflict" if numeric_status == 409 else "runtime_api_problem"
            description = response_payload.get("description")
            summary = description if isinstance(description, str) else "Runtime API problem."
            problem_payload["examples"] = {
                "default": {
                    "summary": summary,
                    "value": runtime_problem_example(
                        status_code=numeric_status,
                        code=code,
                        path=path,
                        request_id=_REQUEST_ID_SAMPLE,
                    ),
                }
            }

        success_pair = _first_success_response(responses)
        if success_pair is None:
            continue
        _success_status, success_response = success_pair
        success_content = success_response.get("content")
        if not isinstance(success_content, dict):
            continue
        success_json = success_content.get("application/json")
        if not isinstance(success_json, dict):
            continue
        if "example" in success_json or success_json.get("examples"):
            pass
        elif isinstance(operation_id, str):
            examples = _SUCCESS_EXAMPLE_SETS_BY_OPERATION.get(operation_id)
            example = _SUCCESS_EXAMPLES_BY_OPERATION.get(operation_id)
            if examples is not None:
                examples_value = examples() if callable(examples) else examples
                success_json["examples"] = deepcopy(examples_value)
            elif example is not None:
                example_value = example() if callable(example) else example
                success_json["examples"] = {
                    "default": {
                        "summary": f"{operation_id} response example",
                        "value": deepcopy(example_value),
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


def _success_response_has_example(status_code: str, response: dict[str, Any]) -> bool:
    """Require an inline example, a schema-declared binary body, or a no-body status."""
    content = response.get("content")
    if status_code in {"204", "205"} and not content:
        return True
    if not isinstance(content, dict):
        return False
    for media_type, payload in content.items():
        if not isinstance(media_type, str) or not isinstance(payload, dict):
            continue
        if "example" in payload:
            return True
        examples = payload.get("examples")
        if isinstance(examples, dict) and any(
            isinstance(example, dict) and "value" in example for example in examples.values()
        ):
            return True
        media_schema = payload.get("schema")
        if (
            media_type != "application/json"
            and isinstance(media_schema, dict)
            and media_schema.get("type") == "string"
            and media_schema.get("format") == "binary"
        ):
            return True
    return False


def validate_runtime_openapi_contract(schema: dict[str, Any]) -> list[str]:
    """Validate runtime OpenAPI examples and typed problem responses."""
    violations: list[str] = []
    success_example_adapters = _success_example_response_adapters()
    components = schema.get("components")
    component_schemas = components.get("schemas") if isinstance(components, dict) else None
    expected_schema = RuntimeApiProblem.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    expected_defs = expected_schema.pop("$defs", {})
    if not isinstance(component_schemas, dict):
        violations.append("components.schemas is missing")
    else:
        if isinstance(expected_defs, dict):
            for name, definition in expected_defs.items():
                if component_schemas.get(name) != definition:
                    violations.append(
                        f"components.schemas.{name} differs from a nested RuntimeApiProblem DTO"
                    )
        if component_schemas.get("RuntimeApiProblem") != expected_schema:
            violations.append(
                "components.schemas.RuntimeApiProblem differs from the RuntimeApiProblem model"
            )
    for path, method, operation in iter_openapi_operations(schema):
        responses = operation.get("responses")
        if not isinstance(responses, dict):
            violations.append(f"{method.upper()} {path}: missing responses object")
            continue
        success_pair = _first_success_response(responses)
        success = success_pair[1] if success_pair is not None else None
        success_example_found = (
            success_pair is not None
            and isinstance(success, dict)
            and _success_response_has_example(success_pair[0], success)
        )
        if not success_example_found:
            violations.append(f"{method.upper()} {path}: missing 2xx success response example")
        operation_id = operation.get("operationId")
        if isinstance(operation_id, str):
            adapter = success_example_adapters.get(operation_id)
            if adapter is not None and isinstance(success, dict) and success_pair is not None:
                status_code, _success_response = success_pair
                content = success.get("content")
                json_payload = (
                    content.get("application/json") if isinstance(content, dict) else None
                )
                if isinstance(json_payload, dict):
                    actual_response_schema = json_payload.get("schema")
                    expected_model_schema = adapter.json_schema(mode="serialization")
                    actual_projection = _success_json_schema_projection(
                        actual_response_schema,
                        document=schema,
                    )
                    expected_projection = _success_json_schema_projection(
                        expected_model_schema,
                        document=expected_model_schema,
                    )
                    if actual_projection != expected_projection:
                        violations.append(
                            f"{method.upper()} {path}: success response schema differs from "
                            "registered response model"
                        )
                    model_examples: list[tuple[str, object]] = []
                    if "example" in json_payload:
                        model_examples.append(("example", json_payload["example"]))
                    examples = json_payload.get("examples")
                    if isinstance(examples, dict):
                        model_examples.extend(
                            (str(name), item["value"])
                            for name, item in examples.items()
                            if isinstance(item, dict) and "value" in item
                        )
                    for name, value in model_examples:
                        try:
                            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
                            adapter.validate_json(encoded, strict=True)
                        except (TypeError, ValueError):
                            violations.append(
                                f"{method.upper()} {path}: {status_code} success example "
                                f"{name} does not match registered response model"
                            )
            links = _SUCCESS_LINKS_BY_OPERATION.get(operation_id, {})
            if links:
                actual_links = success.get("links") if isinstance(success, dict) else None
                if not isinstance(actual_links, dict):
                    violations.append(f"{method.upper()} {path}: missing success response links")
                else:
                    for link_name in links:
                        if link_name not in actual_links:
                            rendered = (
                                f"{method.upper()} {path}: "
                                f"missing success response link {link_name}"
                            )
                            violations.append(rendered)
        for status in _DEFAULT_PROBLEM_RESPONSES:
            response = responses.get(status)
            if not isinstance(response, dict):
                violations.append(f"{method.upper()} {path}: missing {status} response")
                continue
            content = response.get("content")
            if not isinstance(content, dict):
                violations.append(f"{method.upper()} {path}: {status} response missing content")
                continue
            payload = content.get(_RUNTIME_PROBLEM_MEDIA_TYPE)
            if not isinstance(payload, dict):
                violations.append(
                    f"{method.upper()} {path}: {status} response missing "
                    f"{_RUNTIME_PROBLEM_MEDIA_TYPE}"
                )
                continue
            if payload.get("schema") != {"$ref": _RUNTIME_PROBLEM_SCHEMA_REF}:
                violations.append(
                    f"{method.upper()} {path}: {status} response must reference "
                    "components.schemas.RuntimeApiProblem"
                )
            if "example" not in payload and not payload.get("examples"):
                violations.append(
                    f"{method.upper()} {path}: {status} response missing problem example"
                )
        for status, response in responses.items():
            if not isinstance(response, dict):
                continue
            content = response.get("content")
            if not isinstance(content, dict):
                continue
            has_media = _RUNTIME_PROBLEM_MEDIA_TYPE in content
            ref_media = [
                media
                for media, payload in content.items()
                if isinstance(payload, dict)
                and _schema_references_runtime_api_problem(payload.get("schema"))
            ]
            if not has_media and not ref_media:
                continue
            rendered_status = str(status)
            if not has_media:
                violations.append(
                    f"{method.upper()} {path}: {rendered_status} RuntimeApiProblem "
                    f"response must use {_RUNTIME_PROBLEM_MEDIA_TYPE}"
                )
            for media in ref_media:
                if media != _RUNTIME_PROBLEM_MEDIA_TYPE:
                    violations.append(
                        f"{method.upper()} {path}: {rendered_status} RuntimeApiProblem "
                        f"schema is advertised under {media}, not {_RUNTIME_PROBLEM_MEDIA_TYPE}"
                    )
            payload = content.get(_RUNTIME_PROBLEM_MEDIA_TYPE)
            if not isinstance(payload, dict):
                violations.append(
                    f"{method.upper()} {path}: {rendered_status} response has no "
                    f"{_RUNTIME_PROBLEM_MEDIA_TYPE} payload"
                )
                continue
            if payload.get("schema") != {"$ref": _RUNTIME_PROBLEM_SCHEMA_REF}:
                violations.append(
                    f"{method.upper()} {path}: {rendered_status} response must directly "
                    "reference components.schemas.RuntimeApiProblem"
                )
            values: list[tuple[str, object]] = []
            if "example" in payload:
                values.append(("example", payload["example"]))
            examples = payload.get("examples")
            if isinstance(examples, dict):
                values.extend(
                    (str(name), item["value"])
                    for name, item in examples.items()
                    if isinstance(item, dict) and "value" in item
                )
            if not values:
                violations.append(
                    f"{method.upper()} {path}: {rendered_status} response missing "
                    "an inline RuntimeApiProblem example"
                )
                continue
            for name, value in values:
                try:
                    problem = RuntimeApiProblem.model_validate(value, strict=True)
                except (TypeError, ValueError) as exc:
                    violations.append(
                        f"{method.upper()} {path}: {rendered_status} example {name} "
                        f"is not a RuntimeApiProblem ({exc})"
                    )
                    continue
                if rendered_status.isdigit():
                    code = int(rendered_status)
                    if problem.status != code or problem.status_code != code:
                        violations.append(
                            f"{method.upper()} {path}: {rendered_status} example {name} "
                            "has mismatched problem status fields"
                        )
    return violations


__all__ = [
    "augment_runtime_openapi",
    "install_runtime_openapi_contract",
    "validate_runtime_openapi_contract",
]
