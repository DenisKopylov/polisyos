from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.governance.continuous import DecisionValidityStatus
from polisyos.scientist.governance.continuous.reissue import ReissuePacket
from polisyos.scientist.governance.human_review.models import ReviewRiskTier
from polisyos.scientist.governance.human_review.oversight_policy import HumanReviewRequirement
from polisyos.scientist.governance.human_review.voi_escalation import (
    validate_human_escalation_voi_decision,
)
from polisyos.scientist.methods.search.voi_models import VOIDecisionRecord, VOIDecisionType
from polisyos.scientist.orchestration.memory import (
    MemoryContaminationPolicy,
    assert_reusable_memory_clean,
)
from tools.ci import check_scientist_best_in_class_wave2 as gate

REPO_ROOT = Path(__file__).resolve().parents[3]


def _ref(seed: str, *, kind: str = "scientist.fixture") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(
            "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()
        ),
        kind=kind,
        media_type="application/json",
    )


def test_scientist_wave2_gate_passes_repo(tmp_path: Path) -> None:
    output_json = tmp_path / "wave2.json"

    exit_code = gate.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--output",
            str(output_json),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )
    payload = json.loads(output_json.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["assessment_id"] == "scientist_best_in_class_wave2"
    assert payload["passes_all"] is True
    assert payload["category_results"]["wave1_gate_green"] is True
    assert payload["category_results"]["phase_gates_green"] is True
    assert payload["category_results"]["cross_phase_invariants_validate"] is True
    assert payload["category_results"]["migration_notes_complete"] is True
    assert payload["category_results"]["shadow_evidence_complete"] is True
    assert set(payload["phase_gate_reports"]) == {
        "phase2_0",
        "phase2_1",
        "phase2_2",
        "phase2_3",
        "phase2_4",
        "phase2_5",
        "phase2_6",
        "phase2_7",
    }


def test_scientist_wave2_gate_fails_if_phase_gate_fails(monkeypatch) -> None:
    def fake_run_phase_gates(repo_root: Path):
        return False, {"phase2_7": {"passes_all": False}}, ["phase2_7:gate_failed"]

    monkeypatch.setattr(gate, "_run_phase_gates", fake_run_phase_gates)

    payload = gate._build_payload(REPO_ROOT)

    assert payload["passes_all"] is False
    assert payload["category_results"]["phase_gates_green"] is False
    assert "phase2_7:gate_failed" in payload["notes"]


def test_scientist_wave2_gate_reports_missing_migration_token(monkeypatch) -> None:
    monkeypatch.setattr(
        gate,
        "MIGRATION_TOKENS",
        (*gate.MIGRATION_TOKENS, "__missing_wave2_migration_token__"),
    )

    payload = gate._build_payload(REPO_ROOT)

    assert payload["passes_all"] is False
    assert payload["category_results"]["migration_notes_complete"] is False
    assert "missing_migration_token:__missing_wave2_migration_token__" in payload["notes"]


def test_scientist_wave2_gate_detects_unexplained_claim_change() -> None:
    missing = gate._claim_changes_missing_from_replay_diff(
        changed_claim_ids={"claim_changed"},
        replay_changed_claim_ids=["added:claim_other"],
    )

    assert missing == ["claim_changed"]


def test_public_compiler_export_with_hidden_benchmark_ref_fails() -> None:
    ok, notes = gate._import_and_validate(REPO_ROOT)

    assert ok, notes
    assert "public_compiler_hidden_benchmark_ref_not_blocked" not in notes


def test_voi_report_that_skips_mandatory_human_review_fails() -> None:
    requirement = HumanReviewRequirement(
        required=True,
        risk_tier=ReviewRiskTier.HIGH,
        reasons=["high_risk_publication"],
    )
    decision = VOIDecisionRecord(
        decision_id="voi_bad_human_review",
        run_id="run_wave2_negative",
        decision_type=VOIDecisionType.HUMAN_ESCALATION,
        recommended_action="defer",
        expected_value=0.0,
        expected_cost=0.0,
        expected_risk_reduction=0.0,
        explanation="Attempts to skip mandatory human review.",
    )

    assert validate_human_escalation_voi_decision(
        decision,
        requirement=requirement,
    ) == ["required_human_review_suppressed:voi_bad_human_review"]


def test_memory_event_with_hidden_eval_canary_fails() -> None:
    with pytest.raises(ValueError, match="reusable memory contamination"):
        assert_reusable_memory_clean(
            {"lesson": "contains EVAL_CANARY_WAVE2"},
            policy=MemoryContaminationPolicy(canary_tokens={"EVAL_CANARY_WAVE2"}),
        )


def test_reissue_packet_without_new_claim_ledger_linkage_fails() -> None:
    with pytest.raises(ValidationError, match="new decision and claim ledger refs"):
        ReissuePacket(
            original_decision_packet_ref=_ref("old-packet", kind="scientist.decision_packet"),
            original_claim_ledger_ref=_ref("old-ledger", kind="scientist.claim_ledger_v2"),
            new_decision_packet_ref=_ref("new-packet", kind="scientist.decision_packet"),
            status=DecisionValidityStatus.REISSUED,
            monitor_event_refs=[_ref("monitor-event", kind="scientist.governance_monitor_event")],
            reason="Missing new claim ledger link.",
        )
