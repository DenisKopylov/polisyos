from __future__ import annotations

# Canonical input keys (ExperimentState.inputs)
INPUT_TRINITY_BUNDLE_REF = "trinity_bundle_ref"
INPUT_REGISTRY_BUNDLE_REF = "registry_bundle_ref"
INPUT_DATA_SNAPSHOT_REF = "data_snapshot_ref"
INPUT_STATE_SNAPSHOT_REF = "state_snapshot_ref"
INPUT_DATA_VIEW_REQUEST_REF = "data_view_request_ref"
INPUT_KNOWLEDGE_BUNDLE_REF = "knowledge_bundle_ref"
INPUT_RESEARCH_INTENT_REF = "research_intent_ref"
INPUT_NORM_PACK_REF = "norm_pack_ref"

# Legacy compatibility inputs
INPUT_POLICY_IR_REF = "policy_ir_ref"

# Canonical artifact keys (ExperimentState.artifacts_index)
ARTIFACT_EXEC_PLAN_REF = "exec_plan_ref"
ARTIFACT_PROGRAM_GRAPH_REF = "program_graph_ref"
ARTIFACT_SIMULATION_RESULT_REF = "simulation_result_ref"
ARTIFACT_METRICS_REF = "metrics_ref"
ARTIFACT_STATE_DELTA_REF = "state_delta_ref"
ARTIFACT_STATE_SNAPSHOT_REF = "state_snapshot_ref"
ARTIFACT_CONSTRAINT_REPORT_REF = "constraint_report_ref"
ARTIFACT_ENVIRONMENT_MANIFEST_REF = "environment_manifest_ref"
ARTIFACT_SLOT_LAYOUT_REF = "slot_layout_ref"
ARTIFACT_TREASURY_PLAN_REF = "treasury_plan_ref"
ARTIFACT_DECISION_PACKET_REF = "decision_packet_ref"
ARTIFACT_DECISION_CARD_REF = "decision_card_ref"

# Legacy bridge (optional)
ARTIFACT_SIMULATION_SUMMARY_REF = "simulation_summary_ref"

# Canonical report keys (ExperimentState.reports_index)
REPORT_LINK_REPORT_REF = "link_report_ref"
REPORT_COMPILE_REPORT_REF = "compile_report_ref"
REPORT_LEGAL_REPORT_REF = "legal_report_ref"
REPORT_CHANGE_PROPOSAL_REF = "change_proposal_ref"
REPORT_GOVERNANCE_REPORT_REF = "governance_report_ref"


__all__ = [
    "INPUT_TRINITY_BUNDLE_REF",
    "INPUT_REGISTRY_BUNDLE_REF",
    "INPUT_DATA_SNAPSHOT_REF",
    "INPUT_STATE_SNAPSHOT_REF",
    "INPUT_DATA_VIEW_REQUEST_REF",
    "INPUT_KNOWLEDGE_BUNDLE_REF",
    "INPUT_RESEARCH_INTENT_REF",
    "INPUT_NORM_PACK_REF",
    "INPUT_POLICY_IR_REF",
    "ARTIFACT_EXEC_PLAN_REF",
    "ARTIFACT_PROGRAM_GRAPH_REF",
    "ARTIFACT_SIMULATION_RESULT_REF",
    "ARTIFACT_METRICS_REF",
    "ARTIFACT_STATE_DELTA_REF",
    "ARTIFACT_STATE_SNAPSHOT_REF",
    "ARTIFACT_CONSTRAINT_REPORT_REF",
    "ARTIFACT_ENVIRONMENT_MANIFEST_REF",
    "ARTIFACT_SLOT_LAYOUT_REF",
    "ARTIFACT_TREASURY_PLAN_REF",
    "ARTIFACT_DECISION_PACKET_REF",
    "ARTIFACT_DECISION_CARD_REF",
    "ARTIFACT_SIMULATION_SUMMARY_REF",
    "REPORT_LINK_REPORT_REF",
    "REPORT_COMPILE_REPORT_REF",
    "REPORT_LEGAL_REPORT_REF",
    "REPORT_CHANGE_PROPOSAL_REF",
    "REPORT_GOVERNANCE_REPORT_REF",
]
