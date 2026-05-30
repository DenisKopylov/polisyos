# ruff: noqa: S101

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ddm.integration.events import (
    AffectedSlice,
    MonitoringWindow,
    ShiftDetectedEvent,
)
from polisyos.runtime.quality.calibration_ledger import (
    CalibrationHistoryPolicy,
    build_calibration_ledger,
)
from polisyos.scientist.governance.continuous.detectors import (
    FairnessDriftSignal,
    PolicyContextSignal,
    detect_calibration_drift,
    detect_fairness_drift,
    detect_policy_context_drift,
    detect_source_invalidation,
)
from polisyos.scientist.governance.continuous.reports import build_validity_report
from polisyos.scientist.orchestration.memory import (
    BalancedMemoryKind,
    BalancedMemoryScope,
    MemorySourceKind,
    MemoryVisibility,
    build_balanced_memory_record,
)


def _ref(seed: str, *, kind: str = "scientist.decision_packet") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/json",
    )


def _sha(char: str) -> str:
    return "sha256:" + char * 64


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


def _calibration_entry(index: int, *, false_pass: bool = False) -> dict[str, Any]:
    return {
        "ledger_entry_id": f"cal-entry-{index}",
        "source_case_id": f"case-{index}",
        "run_id": f"run-{index}",
        "claim_id": f"claim-{index}",
        "event_kind": "claim_refuted" if false_pass else "claim_confirmed",
        **_scope(),
        "group_keys": ["population:msme", "geography:kyiv-oblast"],
        "predicted_object": {"claim_status": "publishable", "probability": 0.86},
        "realized_object": {
            "claim_status": "refuted" if false_pass else "confirmed",
            "resolved_at": "2026-05-20T00:00:00+00:00",
        },
        "calibration_metrics": {
            "nominal_coverage": 0.9,
            "empirical_coverage": 0.76 if false_pass else 0.91,
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
    }


def test_calibration_detector_emits_sparse_event_without_blocking() -> None:
    ledger = build_calibration_ledger(
        entries=[_calibration_entry(1, false_pass=True)],
        target_scope=_scope(),
        target_run_id="run-future",
        target_claim_id="claim-future",
        generated_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
        ledger_ref=_sha("c"),
    )

    result = detect_calibration_drift(
        decision_packet_ref=_ref("1"),
        calibration_ledger=ledger,
        target_scope=_scope(),
        target_claim_id="claim-future",
    )

    event = result.events[0]
    assert event.event_type == "calibration_drift"
    assert event.severity == "warning"
    assert event.affected_claim_ids == ["claim-future"]
    assert event.scope["domain"] == "msme_credit"
    assert event.metadata["sparse_history_band"] == "Insufficient"
    assert event.metadata["sparse_history_non_blocking"] is True
    assert event.metadata["blocking_consequence_permitted"] is False
    assert "insufficient_calibration_history" in event.metadata["reason_codes"]


def test_calibration_detector_blocks_only_mature_governed_adverse_history() -> None:
    ledger = build_calibration_ledger(
        entries=[
            _calibration_entry(index, false_pass=index <= 31)
            for index in range(1, 211)
        ],
        target_scope=_scope(),
        target_run_id="run-future",
        target_claim_id="claim-future",
        generated_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
        policy=CalibrationHistoryPolicy(
            maturity="mature_governed",
            blocking_enabled=True,
            policy_ref=_sha("p"),
            longitudinal_evidence_ref=_sha("l"),
        ),
        ledger_ref=_sha("c"),
    )

    result = detect_calibration_drift(
        decision_packet_ref=_ref("1"),
        calibration_ledger=ledger,
        target_scope=_scope(),
        target_claim_id="claim-future",
    )

    event = result.events[0]
    report = build_validity_report(decision_packet_ref=_ref("1"), monitor_events=[event])

    assert event.severity == "block"
    assert event.metadata["sparse_history_band"] == "Mature adverse"
    assert event.metadata["influence_status"] == "scoped_block"
    assert report.recommendations[0].reissue_recommended is True


def test_fairness_detector_downgrades_thin_slice_shift_to_warning() -> None:
    result = detect_fairness_drift(
        decision_packet_ref=_ref("2"),
        signals=[
            FairnessDriftSignal(
                signal_id="fairness-thin",
                metric_name="critical_slice_false_block_rate",
                observed_value=0.22,
                threshold=0.10,
                sample_count=40,
                affected_slices=("group:disability",),
                affected_claim_ids=("claim-equity",),
                scope={"domain": "benefits", "jurisdiction": "UA"},
            )
        ],
    )

    event = result.events[0]
    assert event.event_type == "fairness_drift"
    assert event.severity == "warning"
    assert event.affected_claim_ids == ["claim-equity"]
    assert event.scope == {"domain": "benefits", "jurisdiction": "UA"}
    assert event.metadata["sparse_history_band"] == "Thin"
    assert event.metadata["blocking_consequence_permitted"] is False


def test_fairness_detector_consumes_ddm_stream_and_blocks_mature_adverse_shift() -> None:
    timestamp = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    ddm_event = ShiftDetectedEvent(
        event_id="shift-1",
        timestamp=timestamp,
        model_id="model-equity",
        model_version="2026.05",
        detector_id="slice-shift",
        detector_family="two_sample",
        signal="slice_shift",
        representation="decision_features",
        reference_window=MonitoringWindow(start=timestamp, end=timestamp, n=260),
        current_window=MonitoringWindow(start=timestamp, end=timestamp, n=240),
        stationarity_regime_id="regime-1",
        calibration_id="cal-1",
        test_statistic=7.4,
        p_value=0.01,
        threshold=0.50,
        empirical_fp_rate=0.02,
        shift_severity=0.82,
        affected_slices=[AffectedSlice(slice="group:low_income", score=0.82)],
    )

    result = detect_fairness_drift(
        decision_packet_ref=_ref("2"),
        signals=[ddm_event],
        slice_claim_map={"group:low_income": ("claim-equity",)},
        scope={"domain": "benefits", "jurisdiction": "UA"},
    )

    event = result.events[0]
    assert event.severity == "block"
    assert event.affected_claim_ids == ["claim-equity"]
    assert event.metadata["sparse_history_band"] == "Mature adverse"
    assert event.metadata["monitor_signal_ids"] == ["shift-1"]
    assert event.metadata["affected_slices"] == ["group:low_income"]


def test_policy_context_detector_consumes_stream_and_balanced_memory_context() -> None:
    memory = build_balanced_memory_record(
        kind=BalancedMemoryKind.SUCCESS,
        summary="Primary authority watchlist caught supersession quickly.",
        pattern_type="authority_watchlist_success",
        stage_name="policy_context_monitoring",
        source_run_id="run-source",
        candidate_hash="candidate-authority-watch",
        scope=BalancedMemoryScope(
            visibility=MemoryVisibility.DOMAIN,
            domain="benefits",
            workflow_id="scientist_policy_design",
        ),
        source_kind=MemorySourceKind.HUMAN_REVIEW,
    )
    result = detect_policy_context_drift(
        decision_packet_ref=_ref("3"),
        signals=[
            PolicyContextSignal(
                signal_id="context-1",
                change_kind="legal_authority_superseded",
                description="The legal authority backing claim-legal was superseded.",
                severity_score=0.95,
                history_count=240,
                blocking_candidate=True,
                affected_claim_ids=("claim-legal",),
                scope={
                    "domain": "benefits",
                    "jurisdiction": "UA",
                    "workflow_id": "scientist_policy_design",
                },
            )
        ],
        balanced_memories=[memory],
    )

    event = result.events[0]
    assert event.event_type == "policy_context_drift"
    assert event.severity == "block"
    assert event.affected_claim_ids == ["claim-legal"]
    assert event.scope["jurisdiction"] == "UA"
    assert event.metadata["balanced_memory_context"]["applicable_memory_ids"] == [
        memory.memory_id
    ]
    assert (
        "current_claim_evidence"
        in event.metadata["balanced_memory_context"]["authority_boundary"]["may_not_use_for"]
    )


def test_source_invalidation_detector_reads_data_forge_manifest_quality_gate() -> None:
    result = detect_source_invalidation(
        decision_packet_ref=_ref("4"),
        current_manifest=_snapshot_manifest(gate_status="fail"),
        snapshot_history_count=250,
    )

    event = result.events[0]
    assert event.event_type == "source_invalidation"
    assert event.severity == "block"
    assert event.affected_claim_ids == ["claim-data"]
    assert event.scope["data_forge_role"] == "catalog"
    assert event.metadata["invalidation_type"] == "quality_gate_failed"
    assert event.metadata["data_hash"] == "sha256:" + "d" * 64


def test_source_invalidation_detector_keeps_sparse_manifest_failure_nonblocking() -> None:
    result = detect_source_invalidation(
        decision_packet_ref=_ref("4"),
        current_manifest=_snapshot_manifest(gate_status="fail"),
        snapshot_history_count=2,
    )

    event = result.events[0]
    assert event.severity == "warning"
    assert event.metadata["sparse_history_band"] == "Insufficient"
    assert event.metadata["sparse_history_non_blocking"] is True
    assert event.metadata["blocking_consequence_permitted"] is False


def _snapshot_manifest(*, gate_status: str) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.data_forge_snapshot_binding.v1",
        "snapshot_id": "snapshot-2026-05-24",
        "release_id": "data-forge-release-snapshot-2026-05-24",
        "generated_at": "2026-05-24T12:00:00+00:00",
        "bindings": [
            {
                "role": "catalog",
                "snapshot_ref": "cas://sha256/" + "a" * 64,
                "manifest_ref": "cas://sha256/" + "b" * 64,
                "data_hash": "sha256:" + "d" * 64,
                "quality_gates": [
                    {
                        "name": "catalog_publish_quality",
                        "status": gate_status,
                        "artifact_id": "cas://sha256/" + "e" * 64,
                    }
                ],
                "claim_requirement_bindings": [
                    {
                        "claim_id": "claim-data",
                        "authority_level": "closeout",
                        "time_role": "publication_time",
                    }
                ],
            }
        ],
    }
