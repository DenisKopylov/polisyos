from __future__ import annotations

import copy
import json
from pathlib import Path

from tools.quality.validation import check_layer3_gy_openalex_artifacts

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_layer3_gy_openalex_artifacts_recompute_from_recorded_real_sources() -> None:
    report = check_layer3_gy_openalex_artifacts.validate(REPO_ROOT)

    assert report["status"] == "pass"
    assert report["accuracy"]["measurement_basis"] == "human_labeled_gold_set"
    assert report["ingest"]["universality"]["different_real_result_sets"] is True
    assert report["ingest"]["skg_counts"]["no_hit_frontier"] == 1
    assert report["ingest"]["span_validation_probe"]["non_supporting_span_status"] == (
        "rejected_non_supporting"
    )
    assert report["ingest"]["web_firewall_probe"]["unvalidated_web_bundle"] == "blocked"
    assert report["ingest"]["web_firewall_probe"]["web_self_attested"] == "blocked"
    assert report["ingest"]["web_firewall_probe"]["non_web_self_attested"] == "blocked"
    assert report["ingest"]["web_firewall_probe"]["non_web_no_grounding"] == "blocked"
    assert report["ingest"]["web_firewall_probe"]["validated_span_grounded_claim"] == "allowed"


def test_layer3_gy_openalex_artifacts_corrupt_accuracy_drift_fails() -> None:
    report = check_layer3_gy_openalex_artifacts.validate(
        REPO_ROOT,
        corrupt_field_drift_check=True,
    )

    assert report["status"] == "pass"
    assert {"code": "layer3_gy_openalex_corrupt_field_drift_detected"} in report["issues"]


def test_layer3_gy_openalex_accuracy_report_requires_real_agent_provenance() -> None:
    from polisyos.scientist.validation.citation_faithfulness import (
        SPAN_SUPPORT_GATEWAY_MODEL_ID,
    )

    payload = json.loads(
        (REPO_ROOT / check_layer3_gy_openalex_artifacts.ACCURACY_PATH).read_text(
            encoding="utf-8"
        )
    )

    expected_model_id = "MiniMaxAI/MiniMax-M2.7"
    assert expected_model_id == SPAN_SUPPORT_GATEWAY_MODEL_ID
    assert expected_model_id == check_layer3_gy_openalex_artifacts.REAL_AGENT_MODEL_ID
    assert payload["accuracy_provenance"]["model_id"] == expected_model_id
    assert payload["accuracy_provenance"]["real_agent"] is True
    assert payload["accuracy_provenance"]["deterministic_replay"] is False
    assert payload["accuracy_provenance"]["held_out_case_count"] > 0
    assert payload["case_judgments"]

    circular = copy.deepcopy(payload)
    circular["accuracy"]["precision"] = 1.0
    circular["accuracy"]["recall"] = 1.0
    circular["accuracy_provenance"]["real_agent"] = False
    circular["accuracy_provenance"]["deterministic_replay"] = True
    circular["accuracy_provenance"]["judge_client"] = "DeterministicSpanSupportClient"
    circular["case_judgments"] = [
        {
            **case,
            "judge_client": "DeterministicSpanSupportClient",
        }
        for case in circular["case_judgments"]
    ]
    issues: list[dict[str, str]] = []

    check_layer3_gy_openalex_artifacts.validate_accuracy_report_payload(
        circular,
        expected=payload,
        issues=issues,
    )

    assert {"code": "layer3_gy_openalex_accuracy_not_real_agent"} in issues
    assert {"code": "layer3_gy_openalex_accuracy_circular_replay"} in issues



def test_layer3_gy_openalex_accuracy_report_rejects_response_model_drift() -> None:
    payload = json.loads(
        (REPO_ROOT / check_layer3_gy_openalex_artifacts.ACCURACY_PATH).read_text(
            encoding="utf-8"
        )
    )
    payload["accuracy_provenance"]["model_id"] = "MiniMaxAI/MiniMax-M2.7"
    for case in payload["case_judgments"]:
        case["agent_judgment"]["model_id"] = "MiniMaxAI/MiniMax-M2.7"
    payload["case_judgments"][0]["agent_judgment"]["model_id"] = "other/response-model"
    issues: list[dict[str, str]] = []

    check_layer3_gy_openalex_artifacts.validate_accuracy_report_payload(
        payload,
        expected=payload,
        issues=issues,
    )

    assert {"code": "layer3_gy_openalex_accuracy_model_mismatch"} in issues
