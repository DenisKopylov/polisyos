from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.runtime.quality.calibration_ledger import (
    CALIBRATION_LEDGER_SCHEMA_VERSION,
    CalibrationBehaviorPolicy,
    CalibrationHistoryPolicy,
    CalibrationLedgerEntry,
    build_calibration_ledger,
    calibration_behavior_deficit_records,
    calibration_behavior_scorecard_gates,
    calibration_influence_for_scope,
    historical_prior_claim_evidence_issues,
    persist_calibration_ledger,
)
from polisyos.runtime.quality.calibration_ledger import (
    CLAIM_EVIDENCE_SLOT_KEYS as CALIBRATION_CLAIM_EVIDENCE_SLOT_KEYS,
)
from polisyos.runtime.quality.claim_registry import normalize_runtime_claim_registry
from polisyos.runtime.quality.memory_influence import (
    CLAIM_EVIDENCE_SLOT_KEYS as MEMORY_CLAIM_EVIDENCE_SLOT_KEYS,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def test_claim_evidence_slot_projection_has_one_owner() -> None:
    assert CALIBRATION_CLAIM_EVIDENCE_SLOT_KEYS is MEMORY_CLAIM_EVIDENCE_SLOT_KEYS


def test_unknown_historical_prior_payload_value_fails_closed() -> None:
    issues = historical_prior_claim_evidence_issues(
        {"runtime_invented_opaque_position": b"historical-prior-influence:opaque"},
        claim_id="claim-opaque",
    )

    assert issues
    assert issues[0]["code"] == "historical_prior_payload_provenance_unknown"


def _scope(**overrides: str) -> dict[str, str]:
    scope = {
        "domain": "msme_credit",
        "method_family": "causal_effect",
        "jurisdiction": "UA",
        "data_class": "admin_panel",
        "evidence_mode": "claim_bound_runtime",
        "authority_level": "publication",
        "provider": "provider.alpha",
        "claim_family": "recommendation",
    }
    scope.update(overrides)
    return scope


def _entry(index: int, *, false_pass: bool = False) -> dict[str, Any]:
    return {
        "ledger_entry_id": f"cal-entry-{index}",
        "source_case_id": f"case-{index}",
        "run_id": f"run-{index}",
        "claim_id": f"claim-{index}",
        "event_kind": "claim_refuted" if false_pass else "claim_confirmed",
        **_scope(),
        "group_keys": ["population:msme", "geography:kyiv-oblast"],
        "forecast_horizon": "P90D",
        "observation_window": "2026-Q2",
        "predicted_object": {"claim_status": "publishable", "probability": 0.86},
        "realized_object": {
            "claim_status": "refuted" if false_pass else "confirmed",
            "resolved_at": "2026-05-20T00:00:00+00:00",
        },
        "calibration_metrics": {
            "nominal_coverage": 0.9,
            "empirical_coverage": 0.76 if false_pass else 0.91,
            "signed_bias": 0.18 if false_pass else 0.01,
            "absolute_error": 0.18 if false_pass else 0.03,
            "false_pass": false_pass,
            "group_calibration_gap": 0.12 if false_pass else 0.02,
        },
        "decision_metrics": {
            "passed_gate": True,
            "material_failure": false_pass,
            "false_pass": false_pass,
            "error_opportunity": True,
        },
        "evidence_portfolio_signature": "legal_anchor+admin_data+foundry_causal",
        "exchangeability_signature": "scope:msme-credit/UA/admin-panel/causal/v1",
        "status": "active",
        "provenance_refs": [
            f"event://lifecycle/case-{index}",
            f"cas://calibration/outcome-{index}",
        ],
        "review_after": "2026-08-20T00:00:00+00:00",
    }


def test_sparse_history_emits_transparent_nonblocking_influence() -> None:
    ledger = build_calibration_ledger(
        entries=[_entry(1, false_pass=True)],
        target_scope=_scope(),
        target_run_id="run-future",
        target_claim_id="claim-future",
        generated_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
        ledger_ref=_sha("c"),
    )

    influence = calibration_influence_for_scope(
        ledger,
        scope=_scope(),
        target_run_id="run-future",
        target_claim_id="claim-future",
    )

    assert ledger["schema_version"] == CALIBRATION_LEDGER_SCHEMA_VERSION
    assert ledger["status"] == "warn"
    assert ledger["bucket_summaries"][0]["history_state"] == "insufficient_history"
    assert ledger["bucket_summaries"][0]["resolved_case_count"] == 1
    assert influence["schema_version"] == "policyos.runtime.historical_prior_influence.v1"
    assert influence["history_state"] == "insufficient_history"
    assert influence["sparse_history_non_blocking"] is True
    assert influence["blocking_permitted"] is False
    assert influence["claim_evidence_admissible"] is False
    assert influence["current_run_evidence_effect"] == "none"
    assert "review_depth_increase" in influence["permitted_effects"]
    assert "current_run_evidence_closure" in influence["authority_boundary"]["may_not_use_for"]
    assert "insufficient_calibration_history" in influence["reason_codes"]


def test_mature_bad_history_can_cap_future_authority_without_evidence_closure() -> None:
    ledger = build_calibration_ledger(
        entries=[
            _entry(index, false_pass=index <= 30)
            for index in range(1, 211)
        ],
        target_scope=_scope(),
        target_run_id="run-future",
        target_claim_id="claim-future",
        generated_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
        policy=CalibrationHistoryPolicy(
            maturity="mature_governed",
            blocking_enabled=True,
            policy_ref=_sha("p"),
            longitudinal_evidence_ref=_sha("l"),
        ),
    )

    influence = calibration_influence_for_scope(
        ledger,
        scope=_scope(),
        target_run_id="run-future",
        target_claim_id="claim-future",
    )

    assert ledger["status"] == "blocked"
    assert influence["history_state"] == "mature_history"
    assert influence["influence_status"] == "scoped_block"
    assert influence["blocking_permitted"] is True
    assert influence["authority_cap"] == "below_publication"
    assert "scoped_high_authority_block" in influence["permitted_effects"]
    assert "false_pass_rate_above_block_threshold" in influence["reason_codes"]
    assert influence["claim_evidence_admissible"] is False
    assert influence["current_run_evidence_refs"] == []
    assert "satisfying_claim_evidence" in influence["authority_boundary"]["may_not_use_for"]


def test_sparse_calibration_behavior_is_reviewable_but_not_closeout_blocking() -> None:
    ledger = build_calibration_ledger(
        entries=[_entry(1, false_pass=True)],
        target_scope=_scope(),
        target_run_id="run-future",
        target_claim_id="claim-future",
        generated_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
        ledger_ref=_sha("c"),
    )

    gates = calibration_behavior_scorecard_gates(
        {"calibration_ledger": ledger},
        canary_kind="production",
        generated_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
    )
    deficits = calibration_behavior_deficit_records(
        {"calibration_ledger": ledger},
        generated_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
    )

    sparse_gate = next(
        gate for gate in gates if gate["code"] == "calibration_sparse_history_review"
    )
    assert sparse_gate["status"] == "pass"
    assert sparse_gate["blocking"] is False
    assert sparse_gate["sparse_history_non_blocking"] is True
    assert sparse_gate["review_action"] == "heightened_review"
    assert sparse_gate["closeout_effect"] == "advisory_review_not_blocking"
    assert sparse_gate["owner"] == "team-runtime-quality"
    assert sparse_gate["ttl_seconds"] > 0
    assert deficits == []


def test_enabled_mature_calibration_behavior_emits_gate_and_readiness_cap() -> None:
    ledger = build_calibration_ledger(
        entries=[_entry(index, false_pass=index <= 30) for index in range(1, 211)],
        target_scope=_scope(),
        target_run_id="run-future",
        target_claim_id="claim-future",
        generated_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
        policy=CalibrationHistoryPolicy(
            maturity="mature_governed",
            blocking_enabled=True,
            policy_ref=_sha("p"),
            longitudinal_evidence_ref=_sha("l"),
        ),
        ledger_ref=_sha("c"),
    )
    behavior_policy = CalibrationBehaviorPolicy(
        mature_gate_enabled=True,
        governed_config_ref=_sha("g"),
    )

    gates = calibration_behavior_scorecard_gates(
        {"calibration_ledger": ledger, "calibration_behavior_policy": behavior_policy},
        canary_kind="production",
        generated_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
    )
    deficits = calibration_behavior_deficit_records(
        {"calibration_ledger": ledger, "calibration_behavior_policy": behavior_policy},
        generated_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
    )

    block_gate = next(
        gate for gate in gates if gate["code"] == "calibration_mature_history_scoped_block"
    )
    assert block_gate["status"] == "fail"
    assert block_gate["blocking"] is True
    assert block_gate["feature_flag"] == "policy_design_case.calibration_mature_history_gates"
    assert block_gate["feature_flag_enabled"] is True
    assert block_gate["readiness_cap"] == "below_publication"
    assert block_gate["current_run_evidence_effect"] == "none"
    assert "current_run_evidence_closure" in block_gate["authority_boundary"]["may_not_use_for"]

    assert deficits == [
        {
            "deficit_id": "calibration:historical-prior:run-future:claim-future",
            "deficit_family": "longitudinal_calibration",
            "deficit_code": "scoped_block",
            "claim_ids": ["claim-future"],
            "authority_level": "publication",
            "audience_scope": "public",
            "disposition": "hard_block",
            "readiness_cap": "below_publication",
            "max_audience": "below_publication",
            "owner": "team-runtime-quality",
            "ttl_expires_at": "2026-05-29T12:00:00+00:00",
            "runtime_event_ref": "event://runtime/calibration-behavior/historical-prior-run-future-claim-future",
            "evidence_ref": _sha("c"),
            "public_limitation_note": (
                "Longitudinal calibration history may cap future readiness, but "
                "cannot satisfy or refute current-run claim evidence."
            ),
            "review_refs": ["cal-entry-1"],
        }
    ]


def test_historical_prior_refs_fail_claim_registry_evidence_slots() -> None:
    registry = normalize_runtime_claim_registry(
        {
            "schema_version": "policyos.runtime.claim_registry.v1",
            "claims": [
                {
                    "claim_id": "rec_credit_guarantee",
                    "scenario_requirement_refs": ["scenario.req.credit_support"],
                    "data_refs": [
                        "source.msme_panel",
                        "historical-prior-influence:run-future:msme-credit",
                    ],
                    "selected_norm_refs": ["norm.ua.credit_guarantee"],
                    "method_output_refs": ["foundry.did.msme_survival"],
                    "portfolio_refs": ["portfolio.rec_credit_guarantee"],
                    "argument_refs": ["argument.rec_credit_guarantee"],
                    "warrant_refs": ["warrant.rec_credit_guarantee"],
                    "rebuttal_refs": ["rebuttal.rec_credit_guarantee"],
                    "counter_evidence_refs": ["counter.rec_credit_guarantee"],
                    "limitation_refs": ["data-quality.recency.msme_panel"],
                    "accepted_deficit_refs": ["deficit.recency.msme_panel"],
                }
            ],
        },
    )

    issue_codes = {issue["code"] for issue in registry["issues"]}
    assert registry["status"] == "fail"
    assert "historical_prior_ref_not_admissible_as_claim_evidence" in issue_codes
    issue = next(
        issue
        for issue in registry["issues"]
        if issue["code"] == "historical_prior_ref_not_admissible_as_claim_evidence"
    )
    assert issue["evidence_slot"] == "data_refs"
    assert (
        issue["historical_prior_ref"]
        == "historical-prior-influence:run-future:msme-credit"
    )


def test_runtime_invented_historical_prior_claim_slot_fails_closed() -> None:
    novel_key = f"runtime_invented_prior_position_{uuid4().hex}"
    registry = normalize_runtime_claim_registry(
        {
            "schema_version": "policyos.runtime.claim_registry.v1",
            "claims": [
                {
                    "claim_id": "rec_credit_guarantee",
                    "scenario_requirement_refs": ["scenario.req.credit_support"],
                    "data_refs": ["source.msme_panel"],
                    "selected_norm_refs": ["norm.ua.credit_guarantee"],
                    "method_output_refs": ["foundry.did.msme_survival"],
                    "portfolio_refs": ["portfolio.rec_credit_guarantee"],
                    "argument_refs": ["argument.rec_credit_guarantee"],
                    "warrant_refs": ["warrant.rec_credit_guarantee"],
                    "rebuttal_refs": ["rebuttal.rec_credit_guarantee"],
                    "counter_evidence_refs": ["counter.rec_credit_guarantee"],
                    "limitation_refs": ["data-quality.recency.msme_panel"],
                    "accepted_deficit_refs": ["deficit.recency.msme_panel"],
                    novel_key: {
                        "carrier": [
                            "historical-prior-influence:run-future:msme-credit",
                        ],
                    },
                }
            ],
        },
    )

    issue = next(
        issue
        for issue in registry["issues"]
        if issue["code"] == "historical_prior_ref_not_admissible_as_claim_evidence"
    )
    assert registry["status"] == "fail"
    assert issue["evidence_slot"] == novel_key


def test_calibration_ledger_persistence_writes_cas_and_bundle_surface(
    tmp_path: Path,
) -> None:
    class Store:
        def __init__(self) -> None:
            self.payload: dict[str, Any] | None = None
            self.options: Any = None

        def put_json(self, payload: dict[str, Any], options: Any, **_: Any) -> ArtifactRef:
            self.payload = payload
            self.options = options
            return ArtifactRef(
                artifact_id=_sha("a"),
                kind="runtime.calibration_ledger",
                media_type="application/json",
            )

    store = Store()
    ledger = build_calibration_ledger(
        entries=[_entry(1)],
        target_scope=_scope(),
        generated_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
    )

    persistence = persist_calibration_ledger(
        ledger,
        store=store,
        evidence_bundle_path=tmp_path,
    )

    assert str(persistence.calibration_ledger_ref.artifact_id) == _sha("a")
    assert store.payload is not None
    assert store.payload["authority_boundary"]["may_not_use_for"]
    assert store.options.kind == "runtime.calibration_ledger"
    assert persistence.evidence_bundle_ledger_path is not None
    bundle_entry = json.loads(
        persistence.evidence_bundle_ledger_path.read_text(encoding="utf-8")
    )
    assert (
        bundle_entry["schema_version"]
        == "policyos.runtime.calibration_ledger_bundle_entry.v1"
    )
    assert bundle_entry["calibration_ledger_ref"] == _sha("a")


def test_calibration_ledger_entry_rejects_blank_required_scope_fields() -> None:
    payload = _entry(1)
    payload["domain"] = "   "

    with pytest.raises(ValueError, match="domain"):
        CalibrationLedgerEntry.model_validate(payload)
