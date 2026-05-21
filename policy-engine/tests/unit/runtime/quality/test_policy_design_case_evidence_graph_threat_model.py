from __future__ import annotations

# ruff: noqa: S101
from typing import Any

from tests.unit.runtime.quality.test_policy_design_case_false_passes import (
    _policy_design_case,
    _scorecard_blocking_codes_for_case,
    sha,
)

EXPECTED_EVIDENCE_GRAPH_THREATS = {
    "prompt_injection",
    "poisoned_datasets",
    "stale_indexes",
    "malicious_tenants",
    "forged_provenance",
    "compromised_plugins",
    "local_client_leakage",
    "insider_mutation",
}


def test_policy_design_case_blocks_missing_evidence_graph_threat_model_record() -> None:
    case = _policy_design_case(evidence_graph_threat_model=None)
    case.pop("evidence_graph_threat_model", None)

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_evidence_graph_threat_model_record_missing" in codes


def test_policy_design_case_blocks_missing_required_evidence_graph_threat_record() -> None:
    record = _complete_evidence_graph_threat_model_record()
    record["threat_records"] = [
        row for row in record["threat_records"] if row["threat_id"] != "forged_provenance"
    ]
    case = _policy_design_case(evidence_graph_threat_model=record)

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_evidence_graph_threat_model_threat_missing" in codes


def test_policy_design_case_blocks_unmitigated_evidence_graph_threat_record() -> None:
    record = _complete_evidence_graph_threat_model_record()
    compromised_plugin = next(
        row for row in record["threat_records"] if row["threat_id"] == "compromised_plugins"
    )
    compromised_plugin["mitigation_refs"] = []
    case = _policy_design_case(evidence_graph_threat_model=record)

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_evidence_graph_threat_model_mitigation_missing" in codes


def test_complete_evidence_graph_threat_model_record_names_phase_29_1_threats() -> None:
    record = _policy_design_case()["evidence_graph_threat_model"]

    assert {row["threat_id"] for row in record["threat_records"]} == (
        EXPECTED_EVIDENCE_GRAPH_THREATS
    )


def _complete_evidence_graph_threat_model_record() -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_graph_threat_model.v1",
        "record_family": "integrity_self_fmea_and_maturity.v1",
        "record_id": "evidence-graph-threat-model-rec-1",
        "case_id": "pdc-R_hds_red_control",
        "run_id": "R_hds_red_control",
        "job_id": "job-hds-red-control",
        "tenant_id": "tenant-prod",
        "status": "pass",
        "threat_records": [
            _threat_record("prompt_injection", "untrusted source text or prompts"),
            _threat_record("poisoned_datasets", "fabric/data-forge source corpus"),
            _threat_record("stale_indexes", "retrieval and legal/source indexes"),
            _threat_record("malicious_tenants", "shared CAS and tenant-scoped evidence"),
            _threat_record("forged_provenance", "authority envelopes and provenance refs"),
            _threat_record("compromised_plugins", "plugin discovery and tool adapters"),
            _threat_record("local_client_leakage", "offline client persistence surfaces"),
            _threat_record("insider_mutation", "privileged mutation paths"),
        ],
        "residual_blockers": [],
        "evidence_ref": sha("1"),
        "runtime_event_ref": "event://policy-design-case/evidence-graph-threat-model/1",
    }


def _threat_record(threat_id: str, surface: str) -> dict[str, Any]:
    return {
        "threat_id": threat_id,
        "status": "mitigated",
        "affected_surfaces": [surface],
        "attack_paths": [f"{threat_id}:authority-graph-compromise"],
        "detection_refs": [sha("2")],
        "mitigation_refs": [sha("3")],
        "blocker_policy_ref": sha("4"),
        "residual_risk": "bounded",
        "owner": "team-quality-closeout",
        "evidence_ref": sha("5"),
        "runtime_event_ref": f"event://policy-design-case/evidence-graph-threat/{threat_id}",
    }
