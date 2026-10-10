"""Behavioral tests for DDM readiness-to-incident composition."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

import pytest

from polisyos.ddm.contracts.events import (
    DataQualitySignal,
    ReadinessState,
    ReadinessStateEvent,
    ShiftRiskEvent,
)
from polisyos.ddm.integration.incident import (
    build_incident_payload,
    build_root_cause_bundle,
)
from polisyos.ddm.readiness import map_readiness

_MODEL_ID = "incident-mirror-model"
_MODEL_VERSION = "v-test"
_TIMESTAMP = datetime(2026, 10, 10, tzinfo=UTC)


def _readiness_for_scenario(
    scenario: Literal["clear", "watch", "investigate", "retrain", "hard_failure"],
) -> tuple[ReadinessStateEvent, DataQualitySignal | None]:
    if scenario == "clear":
        return (
            map_readiness(
                model_id=_MODEL_ID,
                model_version=_MODEL_VERSION,
                timestamp=_TIMESTAMP,
            ),
            None,
        )
    if scenario == "watch":
        shift = ShiftRiskEvent(
            event_id="synthetic-shift-event",
            shift_event_id="synthetic-shift",
            timestamp=_TIMESTAMP,
            model_id=_MODEL_ID,
            model_version=_MODEL_VERSION,
            detector_id="synthetic-detector",
            signal="synthetic_input_shift",
            stationarity_regime_id="synthetic-regime",
            calibration_id="synthetic-calibration",
            evidence_kind="ert",
            risk_score=0.5,
            risk_level="watch",
        )
        return (
            map_readiness(
                model_id=_MODEL_ID,
                model_version=_MODEL_VERSION,
                shift_events=[shift],
                timestamp=_TIMESTAMP,
            ),
            None,
        )
    if scenario in {"investigate", "retrain"}:
        budget = 0.25 if scenario == "investigate" else 0.50
        return (
            map_readiness(
                model_id=_MODEL_ID,
                model_version=_MODEL_VERSION,
                critical_slice_budget_used=budget,
                timestamp=_TIMESTAMP,
            ),
            None,
        )

    quality = DataQualitySignal(
        signal_id="synthetic-hard-contract-failure",
        timestamp=_TIMESTAMP,
        model_id=_MODEL_ID,
        model_version=_MODEL_VERSION,
        risk_score=1.0,
        hard_failure=True,
        violations=["synthetic required feature is missing"],
        affected_features=["synthetic_feature"],
    )
    return (
        map_readiness(
            model_id=_MODEL_ID,
            model_version=_MODEL_VERSION,
            data_quality_signals=[quality],
            timestamp=_TIMESTAMP,
        ),
        quality,
    )


@pytest.mark.parametrize(
    ("scenario", "state", "severity", "actions", "hooks"),
    [
        pytest.param(
            "clear",
            ReadinessState.R4,
            "none",
            ["continue_monitoring"],
            (False, False, False, False, False, False),
            id="r4-clear",
        ),
        pytest.param(
            "watch",
            ReadinessState.R3,
            "watch",
            ["annotate_dashboard", "increase_label_sampling"],
            (False, True, False, False, False, False),
            id="r3-watch-does-not-ticket-or-page",
        ),
        pytest.param(
            "investigate",
            ReadinessState.R2,
            "investigate",
            [
                "open_investigation_ticket",
                "increase_label_sampling",
                "run_shadow_retrain",
            ],
            (True, True, False, True, False, False),
            id="r2-investigate",
        ),
        pytest.param(
            "retrain",
            ReadinessState.R1,
            "retrain",
            ["freeze_rollout", "trigger_shadow_retrain", "require_owner_signoff"],
            (True, True, False, True, True, False),
            id="r1-retrain-and-freeze",
        ),
        pytest.param(
            "hard_failure",
            ReadinessState.R0,
            "rollback",
            [
                "rollback_or_route_to_fallback",
                "page_model_owner",
                "block_registry_promotion",
            ],
            (True, True, True, False, False, True),
            id="r0-rollback-page-and-attach-root-cause",
        ),
    ],
)
def test_incident_payload_preserves_readiness_severity_action_lattice(
    scenario: Literal["clear", "watch", "investigate", "retrain", "hard_failure"],
    state: ReadinessState,
    severity: str,
    actions: list[str],
    hooks: tuple[bool, bool, bool, bool, bool, bool],
) -> None:
    readiness, quality = _readiness_for_scenario(scenario)

    assert readiness.readiness_state is state
    assert readiness.required_actions == actions

    root_cause = None
    if quality is not None:
        root_cause = build_root_cause_bundle(
            model_id=_MODEL_ID,
            model_version=_MODEL_VERSION,
            data_quality_signals=[quality],
            timestamp=_TIMESTAMP,
        )

    incident = build_incident_payload(
        readiness_event=readiness,
        root_cause_bundle=root_cause,
    )

    assert incident.readiness_state is state
    assert incident.severity == severity
    assert incident.required_actions == actions
    assert (
        incident.create_ticket,
        incident.notify_owner,
        incident.page_owner,
        incident.trigger_shadow_retrain,
        incident.freeze_rollout,
        incident.rollback_or_fallback,
    ) == hooks
    if state is ReadinessState.R0:
        assert root_cause is not None
        assert incident.root_cause_bundle_id == root_cause.event_id
        assert incident.attach_event_ids == [root_cause.event_id]
    else:
        assert incident.root_cause_bundle_id is None
        assert incident.attach_event_ids == []
